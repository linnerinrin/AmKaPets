"""PetWorld 的交互 mixin：拖拽、点击、摸头的状态变化。

这些方法只改动物体状态与计数器，真正的好感结算写在 :mod:`world.core`
里（那里持有 ``MoodTracker``）。拆出来是因为 ``core.py`` 已接近 300 行硬上限
（AGENTS.md §13.1）。
"""

from __future__ import annotations


from .. import physics
from ..actions import PAT_ACTIONS, random_pool_action
from .events import PatEvent
from .runtime import SAMPLE_WINDOW_MS, DragData


class InteractionMixin:
    """拖拽会话与点击/摸头计数（由 PetWorld 继承使用）。"""

    def _drag_data(self, pet_id: str) -> DragData | None:
        """取当前拖拽会话数据（不在拖拽中返回 None）。"""
        return self._drags.get(pet_id)

    def start_drag(self, pet_id: str, px: float, py: float) -> None:
        """开始拖拽：记录指针偏移并清空轨迹采样。

        :raises KeyError: pet_id 不存在。
        """
        pet = self.get_pet(pet_id)
        pet.dragging = True
        pet.flying = False
        pet.vx = pet.vy = 0.0
        drag = DragData(px - pet.x, py - pet.y, pet.x, pet.y)
        drag.samples.append((self._clock_ms(), px, py))
        self._drags[pet_id] = drag

    def drag_to(self, pet_id: str, px: float, py: float) -> None:
        """拖拽移动：更新弹簧目标并追加轨迹样本。

        :raises KeyError: pet_id 不存在或不在拖拽中。
        """
        drag = self._drag_data(pet_id)
        if drag is None:
            raise KeyError(f"宠物不在拖拽中: {pet_id}")
        drag.target_x = px - drag.offset_x
        drag.target_y = py - drag.offset_y
        drag.samples.append((self._clock_ms(), px, py))
        self.trim_samples(drag)

    def end_drag(self, pet_id: str) -> None:
        """结束拖拽：结算拖拽好感飘字，再按轨迹估算初速决定是否进入飞行。

        :raises KeyError: pet_id 不存在。
        """
        pet = self.get_pet(pet_id)
        drag = self._drags.pop(pet_id, None)
        pet.dragging = False
        self.flush_mood_event(pet_id, "drag")
        if drag is None:
            return
        vx, vy = physics.estimate_throw_velocity(
            drag.samples, self._resolved[pet_id].physics.throw_power, self._clock_ms()
        )
        if vx != 0.0 or vy != 0.0:
            pet.vx, pet.vy = vx, vy
            pet.flying = True
        else:
            pet.vx = pet.vy = 0.0
            pet.flying = False

    def register_click(self, pet_id: str) -> int | None:
        """单击宠物：每 CLICKS_PER_BOOST 次才掷一次好感（动作冷却期内不算）。

        :return: 这次点击刚好攒满时的实际好感增量（pat 区间随机），否则 None。
        :raises KeyError: pet_id 不存在。
        """
        if not self._clicks[pet_id].register(self._now_seconds()):
            return None
        return self._moods[pet_id].roll_pat()

    def pat_pet(self, pet_id: str) -> "PatEvent | None":
        """双击摸头：掷一次 pat 区间好感，并从实例动作池里抽一个动作播放。

        :return: 结算结果（动作 key + 好感增量）；摸头冷却内返回 None。
        :raises KeyError: pet_id 不存在。
        """
        if not self._pats[pet_id].register(self._now_seconds()):
            return None
        action = random_pool_action(self.pat_pool_for(pet_id), PAT_ACTIONS)
        delta = self._moods[pet_id].roll_pat()
        return PatEvent(pet_id=pet_id, action_key=action.key, delta=delta)

    def _now_seconds(self) -> float:
        """当前单调秒数：与拖拽采样共用同一个可注入时钟，冷却判定才能被测出来。"""
        return self._clock_ms() / 1000.0

    def click_pending(self, pet_id: str) -> int:
        """还差几次单击才加好感（面板/调试展示用）。"""
        counter = self._clicks.get(pet_id)
        return counter.remaining if counter is not None else 0

    def trim_samples(self, drag: DragData) -> None:
        """丢弃 SAMPLE_WINDOW_MS 窗口之外的轨迹样本。"""
        now = self._clock_ms()
        drag.samples = [s for s in drag.samples if now - s[0] <= SAMPLE_WINDOW_MS]


__all__ = ["InteractionMixin"]
