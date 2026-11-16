"""心情（好感）常量与提示词载体（纯 dataclass，禁 Qt）。

数值语义见 AGENTS.md §6.5。第四轮需求（m00874）把好感数值全部写死：
初始 80、下降 0.1/s、摸头/拖拽/飞行增益都是固定区间 [0, 2]，
用户不能再改，所以本类退化成「常量 + 四档提示词」的载体——
``from_dict`` 只认 ``prompts``，任何数值都回落到默认常量。

``pat_min/pat_max`` 等字段仍然保留：``mood.MoodTracker`` 直接按字段名取值，
保留字段可以让跟踪器逻辑完全不感知「数值已经写死」这件事。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import MOOD_LEVELS

MOOD_INITIAL = 80.0
"""新建宠物的初始好感（0-100）。"""

MOOD_DECAY = 0.1
"""每秒自然下降的好感值：约 13 分钟从 80 掉到 0（用户口径：掉慢一点）。"""

PAT_RANGE = (0, 2)
"""摸头/点击一次的好感增量区间（整数随机）。"""

DRAG_RANGE = (0, 2)
"""拖拽中每秒的好感增量区间。"""

FLIGHT_RANGE = (0, 2)
"""飞行（甩抛后）中每秒的好感增量区间。"""


@dataclass
class MoodSettings:
    """心情系统设置：数值是常量，可配置的只剩四档提示词覆盖。

    增益采用「整数随机区间」，每次触发时在 [min, max] 里 randint；
    区间本身不可配置（第四轮需求：固定 [0, 2]）。
    """

    initial: float = MOOD_INITIAL
    decay_per_second: float = MOOD_DECAY
    pat_min: int = PAT_RANGE[0]
    pat_max: int = PAT_RANGE[1]
    drag_min: int = DRAG_RANGE[0]
    drag_max: int = DRAG_RANGE[1]
    flight_min: int = FLIGHT_RANGE[0]
    flight_max: int = FLIGHT_RANGE[1]
    prompts: dict[str, str] = field(default_factory=dict)

    def pat_range(self) -> tuple[int, int]:
        """摸头增益区间（UI 只读展示用）。"""
        return (self.pat_min, self.pat_max)

    def drag_range(self) -> tuple[int, int]:
        """拖拽每秒增益区间（UI 只读展示用）。"""
        return (self.drag_min, self.drag_max)

    def flight_range(self) -> tuple[int, int]:
        """飞行每秒增益区间（UI 只读展示用）。"""
        return (self.flight_min, self.flight_max)

    @classmethod
    def from_dict(cls, raw: Any) -> "MoodSettings":
        """从配置字典解析：只保留四档提示词，数值一律回落到常量。

        旧配置里的 click_boost / drag_boost_per_second / throw_boost 等键
        直接忽略即可——数值已经写死，没有迁移的意义。
        """
        default = cls()
        if not isinstance(raw, dict):
            return default
        prompts: dict[str, str] = {}
        raw_prompts = raw.get("prompts")
        if isinstance(raw_prompts, dict):
            for level in MOOD_LEVELS:
                text = raw_prompts.get(level)
                if isinstance(text, str) and text.strip():
                    prompts[level] = text
        return cls(prompts=prompts)

    def to_dict(self) -> dict[str, Any]:
        """序列化为配置字典（数值写入常量值，方便用户查看/自证）。"""
        return {
            "initial": self.initial,
            "decay_per_second": self.decay_per_second,
            "pat_min": self.pat_min,
            "pat_max": self.pat_max,
            "drag_min": self.drag_min,
            "drag_max": self.drag_max,
            "flight_min": self.flight_min,
            "flight_max": self.flight_max,
            "prompts": dict(self.prompts),
        }


__all__ = [
    "DRAG_RANGE",
    "FLIGHT_RANGE",
    "MOOD_DECAY",
    "MOOD_INITIAL",
    "MoodSettings",
    "PAT_RANGE",
]
