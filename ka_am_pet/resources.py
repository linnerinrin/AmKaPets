"""资源路径解析：源码运行与 PyInstaller 冻结运行双模式，以及用户可写数据目录。"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

#: 可用环境变量强制指定数据目录（调试或受限环境用）。
DATA_DIR_ENV = "KA_AM_PET_DATA_DIR"

#: 降级时要跟着搬过去的用户数据文件。
_DATA_FILES = ("config.json", "pets.db", "memory.json")

_log = logging.getLogger(__name__)

#: 最近一次 app_data_dir() 的降级说明；正常情况为空串。
_note = ""


def resource_root() -> Path:
    """返回只读资源根目录：源码=项目根（本文件上两级），冻结=sys._MEIPASS。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def asset_path(*parts: str) -> Path:
    """拼接资源根目录下的资源路径。

    :param parts: 资源相对路径的各段，如 "pets", "main", "idle"。
    :return: 资源绝对路径。
    """
    return resource_root().joinpath("assets", *parts)


def data_dir_note() -> str:
    """返回数据目录的降级说明（正常情况为空串）。

    :return: 给 UI 展示的一句中文提示；无需提示时返回 ""。
    """
    return _note


def _is_writable(directory: Path) -> bool:
    """目录是否真的可写：建目录 + 写探针文件（比 os.access 可靠）。

    :param directory: 待检测目录。
    :return: 能创建并删除探针文件时为 True。
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / f".write-probe-{os.getpid()}"
        probe.write_bytes(b"ok")
        probe.unlink()
        return True
    except OSError:
        return False


def _data_dir_candidates() -> list[Path]:
    """按优先级列出候选数据目录：配置目录 → 本地目录 → 临时 → 项目内。"""
    candidates: list[Path] = []
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        candidates.append(Path(override))

    base = os.environ.get("APPDATA")
    roaming = Path(base) if base else Path.home() / "AppData" / "Roaming"
    candidates.append(roaming / "ka-am-pet")

    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "ka-am-pet")

    # 源码运行时，项目内隐藏目录通常最稳（沙箱里也只有它能写，且跨会话保留）
    if not getattr(sys, "frozen", False):
        candidates.append(resource_root() / ".userdata")

    candidates.append(Path(tempfile.gettempdir()) / "ka-am-pet")
    return candidates


def _seed_from(source: Path, target: Path) -> None:
    """把原目录里已有的用户数据搬到降级目录（目标已有同名文件则跳过）。

    :param source: 原本想用的数据目录（可能写不进去）。
    :param target: 实际可写的降级目录。
    """
    for name in _DATA_FILES:
        src = source / name
        dst = target / name
        if not src.is_file() or dst.exists():
            continue
        try:
            shutil.copyfile(src, dst)
            dst.chmod(dst.stat().st_mode | stat.S_IWRITE)
            _log.info("数据目录降级：已复制 %s -> %s", src, dst)
        except OSError as exc:
            _log.warning("数据目录降级：复制 %s 失败（%s）", src, exc)


def app_data_dir() -> Path:
    """返回用户可写数据目录（config.json / pets.db / memory.json 都在这里）。

    依次探测：KA_AM_PET_DATA_DIR → %APPDATA%\\ka-am-pet →
    %LOCALAPPDATA%\\ka-am-pet → 项目内 .userdata（源码运行）→ %TEMP%\\ka-am-pet。
    前一个写不进去（沙箱、只读盘、权限被改）就顺延下一个，
    保证应用一定起得来；降级原因可通过 data_dir_note() 展示。

    :return: 第一个真正可写的目录；全部不可写时返回首选目录（上层报错提示）。
    """
    global _note

    candidates = _data_dir_candidates()
    for index, candidate in enumerate(candidates):
        if not _is_writable(candidate):
            continue
        if index == 0:
            _note = ""
        else:
            _seed_from(candidates[0], candidate)
            _note = (
                f"无法写入 {candidates[0]}（权限不足或只读），"
                f"数据已暂时改用 {candidate}。"
            )
            _log.warning(_note)
        return candidate

    _note = "找不到可写的数据目录，请检查用户目录权限： " + ", ".join(
        str(path) for path in candidates
    )
    _log.error(_note)
    return candidates[0]
