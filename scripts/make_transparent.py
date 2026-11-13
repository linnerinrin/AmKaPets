# -*- coding: utf-8 -*-
"""开发工具：把 assets/pets/<pet>/<pet>-<mood>.png 处理成透明底、统一尺寸。

步骤（每张图）：
1. 从四边边缘做"近白色"洪水填充，得到背景掩码 -> 透明化（不误伤人物内部浅色）。
2. 对 alpha 做轻微腐蚀+边缘羽化，去掉白边。
3. 按非透明区域包围盒裁剪，留少量 padding。
4. 等比缩放（不拉伸变形）放进统一的正方形透明画布，人物垂直居中、底部留 2% 边距。

输出覆盖写回原路径（先备份原图到 assets/pets/_original/）。
用捆绑 Python 运行（含 Pillow + numpy），不进运行时依赖。
"""

from __future__ import annotations

import shutil
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

CANVAS = 640          # 统一画布边长（正方形）
SUBJECT_FRAC = 0.94   # 人物最长边占画布比例
TOLERANCE = 28        # 近白色判定容差（0-255 通道距离）
FEATHER = 1           # alpha 边缘羽化像素
# 封闭白岛清除按宠物开关：kangel 的封闭中性白全是螺旋马尾缝隙（要清）；
# ame 的封闭中性白是衬衫/泡泡袖（必须保留），故关闭。
ISLAND_REMOVAL = {"kangel": True, "ame": False}


def bg_mask_flood(rgb: np.ndarray, tol: int) -> np.ndarray:
    """从图像四边洪水填充近白色区域，返回背景布尔掩码。"""
    h, w, _ = rgb.shape
    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    def near_white(y: int, x: int) -> bool:
        r, g, b = int(rgb[y, x, 0]), int(rgb[y, x, 1]), int(rgb[y, x, 2])
        return r >= 255 - tol and g >= 255 - tol and b >= 255 - tol

    for x in range(w):
        for y in (0, h - 1):
            if near_white(y, x) and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if near_white(y, x) and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))

    while q:
        y, x = q.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and near_white(ny, nx):
                visited[ny, nx] = True
                q.append((ny, nx))
    return visited


def enclosed_white_islands(rgb: np.ndarray, bg: np.ndarray, tol: int) -> np.ndarray:
    """找被人物围住的白色孤岛（洪水填充够不到的缝隙），返回应清除的掩码。

    双重判定（同时满足才清除）：
    1. 孤岛均色是中性白（通道极差 <= 6，均亮 >= 245）——排除暖白的皮肤/脸；
    2. 孤岛向外膨胀 RING_PX 的检测环上，深色描边（max 通道 < 120）占比 >= DARK_FRAC
       ——排除被浅色衣服包围的白色高光。
    """
    RING_PX = 5
    DARK_FRAC = 0.05
    h, w, _ = rgb.shape
    near_white = (
        (rgb[:, :, 0] >= 255 - tol) & (rgb[:, :, 1] >= 255 - tol) & (rgb[:, :, 2] >= 255 - tol)
    )
    candidate = near_white & ~bg
    visited = np.zeros((h, w), dtype=bool)
    remove = np.zeros((h, w), dtype=bool)

    for sy in range(h):
        for sx in range(w):
            if not candidate[sy, sx] or visited[sy, sx]:
                continue
            # BFS 收集一个孤岛
            comp: list[tuple[int, int]] = []
            q: deque[tuple[int, int]] = deque([(sy, sx)])
            visited[sy, sx] = True
            while q:
                y, x = q.popleft()
                comp.append((y, x))
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < h and 0 <= nx < w and candidate[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        q.append((ny, nx))
            comp_mask = np.zeros((h, w), dtype=bool)
            ys = np.fromiter((p[0] for p in comp), dtype=np.intp)
            xs = np.fromiter((p[1] for p in comp), dtype=np.intp)
            comp_mask[ys, xs] = True
            # 条件 1：中性纯白
            px = rgb[ys, xs].astype(np.int32)
            if px.mean() < 245 or (px.max(axis=1) - px.min(axis=1)).mean() > 6:
                continue
            # 条件 2：检测环上的深色描边占比
            dil = comp_mask.copy()
            for _ in range(RING_PX):
                d = dil.copy()
                d[1:, :] |= dil[:-1, :]
                d[:-1, :] |= dil[1:, :]
                d[:, 1:] |= dil[:, :-1]
                d[:, :-1] |= dil[:, 1:]
                dil = d
            ring = dil & ~comp_mask & ~bg & ~near_white
            if ring.any() and (rgb[ring].max(axis=1) < 120).mean() >= DARK_FRAC:
                remove |= comp_mask
    return remove


def erode_alpha(alpha: np.ndarray, px: int) -> np.ndarray:
    """简单腐蚀：像素四邻域有透明则自己也变透明，去白边。"""
    out = alpha.copy()
    for _ in range(px):
        a = out
        eroded = a.copy()
        eroded[1:, :] &= a[:-1, :]
        eroded[:-1, :] &= a[1:, :]
        eroded[:, 1:] &= a[:, :-1]
        eroded[:, :-1] &= a[:, 1:]
        out = eroded
    return out


def process(path: Path, island_removal: bool) -> tuple[int, int]:
    img = Image.open(path).convert("RGBA")
    rgb = np.asarray(img)[:, :, :3]
    bg = bg_mask_flood(rgb, TOLERANCE)
    if island_removal:
        bg |= enclosed_white_islands(rgb, bg, TOLERANCE)
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    alpha = erode_alpha(alpha, FEATHER)

    arr = np.dstack([rgb, alpha])
    ys, xs = np.where(alpha > 0)
    if len(ys) == 0:
        raise ValueError(f"{path.name}: 抠完啥都不剩了")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    pad = 4
    y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
    y1, x1 = min(arr.shape[0], y1 + pad), min(arr.shape[1], x1 + pad)
    sub = Image.fromarray(arr[y0:y1, x0:x1], "RGBA")

    scale = (CANVAS * SUBJECT_FRAC) / max(sub.width, sub.height)
    new_size = (max(1, round(sub.width * scale)), max(1, round(sub.height * scale)))
    sub = sub.resize(new_size, Image.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    ox = (CANVAS - sub.width) // 2
    oy = CANVAS - sub.height - int(CANVAS * 0.02)  # 底部留 2%
    canvas.alpha_composite(sub, (ox, oy))
    canvas.save(path, "PNG")
    return x1 - x0, y1 - y0


def main() -> int:
    root = Path(__file__).resolve().parent.parent / "assets" / "pets"
    backup = root / "_original"
    for pet_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "_original"):
        for png in sorted(pet_dir.glob("*.png")):
            bak = backup / pet_dir.name / png.name
            if not bak.exists():
                bak.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(png, bak)
            w, h = process(png, ISLAND_REMOVAL.get(pet_dir.name, False))
            print(f"  {png.relative_to(root)}  subject={w}x{h}")
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
