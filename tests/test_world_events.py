"""PetWorld 结算事件测试：拖拽/飞行结束时的好感飘字与摸头事件（纯逻辑，不碰 Qt）。

对应第四轮需求（AGENTS.md 13.9）：增量由 world 累计，结束时产出一条 MoodEvent，
增量为 0 不发；摸头返回 PatEvent（动作来自实例的摸头动作池）。
"""

from __future__ import annotations

import pytest

from ka_am_pet.config import default_config
from ka_am_pet.models import PetConfig, PetOverrides
from ka_am_pet.world.core import PetWorld
from ka_am_pet.world.events import KIND_DRAG, KIND_FLIGHT


def _world() -> tuple[PetWorld, list[float]]:
    """造一个只有一只宠物的小世界，时钟可手动推进。"""
    clock = [1000.0]
    world = PetWorld(default_config(), clock=lambda: clock[0])
    world.add_pet(PetConfig(id="p1", name="测试", size=320, x=400, y=300))
    world.set_bounds((0, 0, 1200, 800))
    return world, clock


def test_drag_end_emits_single_mood_event():
    """拖拽 2 秒后松手：只结算一条 drag 事件，文案是「提起 +N → 值」。"""
    world, clock = _world()
    # 每次拖 2 秒掷两次 [0,2]，两次都掷出 0 时按设计不发事件（1/9 概率），
    # 所以这里重试几次，确保能观察到一条真实的结算事件。
    events = []
    for _ in range(6):
        world.start_drag("p1", 420, 320)
        for step in range(40):
            clock[0] += 0.05
            world.drag_to("p1", 420 + step * 2, 320)
            world.update(0.05)
        world.end_drag("p1")
        events = world.drain_events()
        if events:
            break

    assert len(events) == 1
    event = events[0]
    assert event.kind == KIND_DRAG
    assert 1 <= event.delta <= 4  # 每秒掷一次 [0,2]，两秒最多 4；0 不发事件
    assert event.text().startswith("提起 +")
    assert "→" in event.text()
    # 取走即清空：同一批事件不会被重复播放
    assert world.drain_events() == []


def test_flight_end_emits_flight_event():
    """甩抛飞行到落地静止：结束时结算一条 flight 事件。"""
    world, clock = _world()
    world.start_drag("p1", 420, 320)
    for step in range(6):
        clock[0] += 0.016
        world.drag_to("p1", 420 - step * 60, 320 - step * 30)
        world.update(0.016)
    world.end_drag("p1")
    assert world.get_pet("p1").flying is True
    world.drain_events()  # 丢掉拖拽那条

    for _ in range(1200):
        clock[0] += 0.016
        world.update(0.016)
        if not world.get_pet("p1").flying:
            break
    assert world.get_pet("p1").flying is False

    events = world.drain_events()
    assert [e.kind for e in events] == [KIND_FLIGHT]
    assert events[0].text().startswith("飞行 +")


def test_zero_delta_is_not_reported():
    """增量为 0 不发事件（避免「+0」噪音）。"""
    world, clock = _world()
    world.start_drag("p1", 420, 320)
    clock[0] += 0.02
    world.drag_to("p1", 421, 320)  # 极短拖拽：不到一秒，掷不出增量
    world.update(0.02)
    world.end_drag("p1")
    assert [e for e in world.drain_events() if e.delta == 0] == []


def test_pat_uses_instance_pat_pool():
    """摸头动作来自实例动作池：默认只有「点头摇摆」，加进来后就会被抽到。"""
    world, clock = _world()
    first = world.pat_pet("p1")
    assert first is not None and first.action_key == "nod"

    world.set_overrides("p1", PetOverrides(pat_pool=("sway",)))
    keys = set()
    for _ in range(20):
        clock[0] += 1.0  # 摸头有独立冷却（= 最长动作时长），每次推进一秒
        event = world.pat_pet("p1")
        if event is not None:
            keys.add(event.action_key)
    assert keys == {"sway"}


def test_practice_freezes_world_mood():
    """直播练习：world 层转发后心情恒 100，关闭恢复。"""
    world, clock = _world()
    before = world.mood_tracker("p1").value
    world.set_practice("p1", True)
    assert world.practice_on("p1") is True
    clock[0] += 30
    world.update(30)
    assert world.mood_tracker("p1").value == pytest.approx(100.0)
    world.set_practice("p1", False)
    assert world.practice_on("p1") is False
    assert world.mood_tracker("p1").value == pytest.approx(before)
