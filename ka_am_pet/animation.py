"""帧动画资源与状态机：manifest 加载、随机点击回应、动画状态推进（纯 Python，禁 Qt）。"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AnimationManifest:
    """单个动作（如 idle/happy）的帧动画描述。

    :param name: 动作名（目录名）。
    :param fps: 播放帧率（帧/秒）。
    :param loop: 是否循环播放。
    :param frames: 相对动作目录的帧文件名列表，按播放顺序。
    :param width: 帧图片原始宽度（像素）。
    :param height: 帧图片原始高度（像素）。
    """

    name: str
    fps: float
    loop: bool
    frames: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0

    @property
    def frame_duration(self) -> float:
        """单帧时长（秒）；fps 非法时回退 1/24。"""
        if self.fps <= 0:
            return 1.0 / 24.0
        return 1.0 / self.fps

    @property
    def total_duration(self) -> float:
        """整段动画总时长（秒）。"""
        return self.frame_duration * len(self.frames)


def load_manifest(action_dir: Path) -> AnimationManifest:
    """从动作目录读取 manifest.json 并构造 AnimationManifest。

    :param action_dir: 动作目录（应包含 manifest.json）。
    :return: 解析后的 AnimationManifest。
    :raises FileNotFoundError: manifest.json 不存在。
    :raises ValueError: manifest 字段缺失或非法。
    """
    path = action_dir / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"manifest 不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest JSON 损坏: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"manifest 必须是 JSON 对象: {path}")

    name = data.get("name")
    fps = data.get("fps")
    frames = data.get("frames")
    if not isinstance(name, str) or not name:
        raise ValueError(f"manifest 缺少合法 name: {path}")
    if not isinstance(fps, (int, float)) or fps <= 0:
        raise ValueError(f"manifest fps 非法: {path}")
    if not isinstance(frames, list) or not frames or not all(isinstance(f, str) for f in frames):
        raise ValueError(f"manifest frames 非法: {path}")
    width = data.get("width", 0)
    height = data.get("height", 0)
    if not isinstance(width, int) or not isinstance(height, int) or width < 0 or height < 0:
        raise ValueError(f"manifest width/height 非法: {path}")

    return AnimationManifest(
        name=name,
        fps=float(fps),
        loop=bool(data.get("loop", False)),
        frames=list(frames),
        width=width,
        height=height,
    )


class AnimationStateMachine:
    """点击随机动画状态机：idle 循环，点击随机播放一段回应动画，播完回 idle。

    随机选择保证不连续重复上一段回应（只有一段回应时除外）；新点击可打断旧回应。
    """

    def __init__(self, idle: str = "idle", reactions: list[str] | None = None) -> None:
        """初始化状态机。

        :param idle: 默认循环动画名。
        :param reactions: 可随机选择的回应动画名列表；None 时为空列表。
        """
        self._idle = idle
        self._reactions = list(reactions) if reactions else []
        self._current = idle
        self._last_reaction: str | None = None
        self._elapsed = 0.0
        self._rng = random.Random()

    @property
    def current(self) -> str:
        """当前动画名（idle 或正在播放的回应动画名）。"""
        return self._current

    def on_click(self) -> str:
        """处理点击：随机选一个回应动画并立即切换（可打断当前回应，不连续重复）。

        :return: 新选中的动画名（无可用回应时返回 idle）。
        """
        if not self._reactions:
            self._current = self._idle
            self._elapsed = 0.0
            return self._current
        pool = [r for r in self._reactions if r != self._last_reaction]
        if not pool:  # 只有一段回应时允许重复
            pool = self._reactions
        chosen = self._rng.choice(pool)
        self._last_reaction = chosen
        self._current = chosen
        self._elapsed = 0.0
        return chosen

    def update(self, dt: float, manifest: AnimationManifest | None = None) -> str:
        """按真实时间差推进动画；非循环回应播完后回到 idle。

        :param dt: 距上次更新的真实时间（秒），调用方应已做上限钳制。
        :param manifest: 当前动画的 manifest（用于帧时长与 loop 判断），可选。
        :return: 推进后的当前动画名。
        """
        self._elapsed += max(0.0, dt)
        if self._current != self._idle and manifest is not None:
            if not manifest.loop and self._elapsed >= manifest.total_duration:
                self._current = self._idle
                self._elapsed = 0.0
        return self._current
