"""好感增量事件的窗口分发（desktop / overlay 两种壳共用）。

为什么单独成模块：拖拽与飞行结束时的「累计好感增加」事件由
:class:`ka_am_pet.world.PetWorld` 在物理推进里结算，而飘字画在各自的宠物
窗口里。两种壳都持有同一批 PetWidget，如果两边各抄一遍遍历逻辑，就会在两处
同时维护「事件 → 窗口」的对应关系。

调用约定（顺序很重要）：
1. ``world.update(dt)`` 推进物理并结算事件；
2. :func:`flush_mood_events` 取出本帧事件并交给对应窗口飘字；
3. 各窗口 ``tick()`` 推进动画并重绘。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ka_am_pet.world import PetWorld


def flush_mood_events(world: PetWorld, widgets: Sequence[object]) -> None:
    """把世界层本帧累计的好感事件分发给对应宠物窗口。

    :param world: 共享的物理世界，事件由 :meth:`PetWorld.drain_events` 取空。
    :param widgets: 当前壳持有的宠物窗口（需有 ``pet_id`` 与 ``play_mood_event``）。
    """
    events: Iterable[object] = world.drain_events()
    for event in events:
        pet_id = getattr(event, "pet_id", None)
        for widget in widgets:
            if getattr(widget, "pet_id", None) == pet_id:
                widget.play_mood_event(event)
                break
