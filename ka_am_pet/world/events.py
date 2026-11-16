"""世界事件：拖拽/飞行结束时结算出的「好感累计增量」，供壳层弹一次飘字。

第四轮需求（m00874 第 6 条）：拖拽或飞行结束后显示一次「提起 +10 → 20」
「飞行 +5 → 25」。增量在 :class:`~ka_am_pet.world.core.PetWorld` 里按秒累计，
结束时压成一条 :class:`MoodEvent`，壳层每帧调用 ``drain_events()`` 取走。

纯数据 + 常量，禁 Qt。
"""

from __future__ import annotations

from dataclasses import dataclass

KIND_DRAG = "drag"
KIND_FLIGHT = "flight"

LABEL_DRAG = "提起"
LABEL_FLIGHT = "飞行"

_LABELS = {KIND_DRAG: LABEL_DRAG, KIND_FLIGHT: LABEL_FLIGHT}


@dataclass(frozen=True)
class MoodEvent:
    """一次「拖拽/飞行结束」的好感结算。

    :ivar pet_id: 宠物 id。
    :ivar kind: ``KIND_DRAG`` 或 ``KIND_FLIGHT``。
    :ivar delta: 这次拖拽/飞行期间累计的好感增量（可能为 0）。
    :ivar value: 结算后的好感值（0-100）。
    """

    pet_id: str
    kind: str
    delta: int
    value: float

    def label(self) -> str:
        """动作名（「提起」/「飞行」），供飘字拼接。"""
        return _LABELS.get(self.kind, "")

    def text(self) -> str:
        """飘字文本，例如 ``提起 +10 → 20``。"""
        sign = "+" if self.delta >= 0 else ""
        return f"{self.label()} {sign}{self.delta} → {self.value:.0f}"


@dataclass(frozen=True)
class PatEvent:
    """一次摸头（双击）的结算：实际播放的动作 + 好感增量。

    动作来自实例自己的摸头动作池（默认只有「点头摇摆」）。
    """

    pet_id: str
    action_key: str
    delta: int


__all__ = ["KIND_DRAG", "KIND_FLIGHT", "LABEL_DRAG", "LABEL_FLIGHT", "MoodEvent", "PatEvent"]
