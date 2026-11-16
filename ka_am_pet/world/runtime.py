"""PetWorld 运行时辅助类型：拖拽会话数据与「全局+覆盖」解析后的生效设置。

这些类型是 :class:`~ka_am_pet.world.core.PetWorld` 的内部零件，
单独成模块以保持 world 包内各文件 ≤300 行（AGENTS.md 第 13 节）。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import AudioSettings, MoodSettings, PhysicsParams

#: 拖拽轨迹采样保留窗口（毫秒）。AGENTS.md 第 5 节：松手初速估算用最近 150ms，
#: 窗口留 200ms 以覆盖估算所需样本。
SAMPLE_WINDOW_MS = 200


class DragData:
    """单只宠物的一次拖拽会话数据（指针偏移、弹簧目标、轨迹样本）。"""

    __slots__ = ("offset_x", "offset_y", "target_x", "target_y", "samples")

    def __init__(self, offset_x: float, offset_y: float, x: float, y: float) -> None:
        self.offset_x = offset_x  # 按下点相对宠物左上角的偏移
        self.offset_y = offset_y
        self.target_x = x  # 弹簧目标（宠物左上角目标位置）
        self.target_y = y
        #: 轨迹样本 (t_ms, pointer_x, pointer_y)，仅保留最近 SAMPLE_WINDOW_MS
        self.samples: list[tuple[int, float, float]] = []


@dataclass
class PetRuntimeSettings:
    """某只宠物「全局设置 + 实例覆盖」解析后的生效设置（PetWorld 内部缓存）。

    全局设置保存后由 ``PetWorld.refresh_settings()`` 重建，避免每帧重复合并。
    """

    physics: PhysicsParams
    audio: AudioSettings
    mood: MoodSettings
