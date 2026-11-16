"""好感相关分组：摸头 / 拖拽 / 飞行（数值全部写死，只做展示）。

用户口径（第四轮）：好感消耗不再让用户改，固定区间 [0,2]；这三个分组与
「物理」「摇摆」并列摆在实例设置的「交互」页里。摸头额外带一个动作池，
和摇摆的动作池同款（勾选列表，可多选）。
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QLabel, QWidget

from ...models import MUSIC_POOL, MoodSettings
from ...theme import Theme
from .pool import ActionPool
from .base_section import Section


def _cost_text(low: int, high: int, unit: str) -> str:
    """把写死的区间渲染成只读文案，例如「+0~2 / 每次」。"""
    return f"+{low}~{high} / {unit}"


class PatSection(Section):
    """摸头（双击）：动作池 + 固定好感消耗。"""

    def __init__(
        self,
        mood: MoodSettings,
        pat_pool: Sequence[str],
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """构造摸头分组。

        :param mood: 心情设置（这里只用它写死的区间）。
        :param pat_pool: 当前实例勾选的动作 key。
        :param theme: 界面主题（给动作池列表上色）。
        :param parent: Qt 父控件。
        """
        super().__init__("摸头", parent)
        low, high = mood.pat_range()
        self.pool = ActionPool(MUSIC_POOL, pat_pool, theme)
        self.add_row("好感消耗", QLabel(_cost_text(low, high, "每次")))
        self.add_block("摸头动作（勾选的动作会被随机播放，可多选）", self.pool)

    def pool_keys(self) -> list[str]:
        """读回勾选的动作 key（空列表由调用方回退默认池）。"""
        return self.pool.checked_keys()


class DragSection(Section):
    """拖拽：每秒累计的好感增量（写死，只读展示）。"""

    def __init__(self, mood: MoodSettings, parent: QWidget | None = None) -> None:
        """构造拖拽分组。"""
        super().__init__("拖拽", parent)
        low, high = mood.drag_range()
        self.add_row("好感消耗", QLabel(_cost_text(low, high, "秒")))


class FlightSection(Section):
    """飞行（甩抛后在空中）：每秒累计的好感增量（写死，只读展示）。"""

    def __init__(self, mood: MoodSettings, parent: QWidget | None = None) -> None:
        """构造飞行分组。"""
        super().__init__("飞行", parent)
        low, high = mood.flight_range()
        self.add_row("好感消耗", QLabel(_cost_text(low, high, "秒")))


__all__ = ["DragSection", "FlightSection", "PatSection"]
