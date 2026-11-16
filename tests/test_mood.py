"""心情系统测试（纯函数，不碰 Qt）。"""

import math

from ka_am_pet import mood
from ka_am_pet.models import MoodSettings


def test_linear_decay():
    """心情值随时间线性下降：update(dt) 后值减少 decay_per_second*dt。"""
    t = mood.MoodTracker(MoodSettings(initial=80.0, decay_per_second=0.1))
    t.update(10.0)
    assert math.isclose(t.value, 79.0)


def test_value_clamped_to_0_100():
    """心情值始终钳制在 [0, 100]：衰减不破底、增益不破顶。"""
    t = mood.MoodTracker(MoodSettings(initial=80.0, pat_min=50, pat_max=50))
    t.roll_pat()
    assert t.value == 100.0
    t2 = mood.MoodTracker(MoodSettings(initial=1.0, decay_per_second=10.0))
    t2.update(10.0)
    assert t2.value == 0.0
    assert mood.clamp_mood(-5) == 0.0
    assert mood.clamp_mood(105) == 100.0


def test_level_boundaries():
    """四档边界：100/75→happy，74/50→smile，49/25→sad，24/0→angry。"""
    assert mood.mood_level(100) == "happy"
    assert mood.mood_level(75) == "happy"
    assert mood.mood_level(74) == "smile"
    assert mood.mood_level(50) == "smile"
    assert mood.mood_level(49) == "sad"
    assert mood.mood_level(25) == "sad"
    assert mood.mood_level(24) == "angry"
    assert mood.mood_level(0) == "angry"


def test_roll_pat_uses_range_and_rng():
    """摸头/点击好感：在 [pat_min, pat_max] 内整数随机，可注入 rng 复现。"""
    rolls = iter([2, -1])
    t = mood.MoodTracker(
        MoodSettings(initial=50.0, pat_min=-1, pat_max=2), rng=lambda lo, hi: next(rolls)
    )
    assert t.roll_pat() == 2
    assert t.value == 52.0
    assert t.roll_pat() == -1
    assert t.value == 51.0
    assert t.last_delta == -1


def test_drag_and_flight_roll_per_second():
    """拖拽与飞行各按满 1 秒掷一次 [min,max] 整数，不足 1 秒累积到下一秒。"""
    rolls = iter([1, -1, 1])
    t = mood.MoodTracker(
        MoodSettings(initial=50.0, drag_min=-1, drag_max=1, flight_min=-1, flight_max=1),
        rng=lambda lo, hi: next(rolls),
    )
    assert t.on_drag(0.6) == 0  # 未满 1 秒不掷
    assert t.on_drag(0.6) == 1  # 满 1 秒掷第一次
    assert t.value == 51.0
    assert t.on_flight(1.0) == -1
    assert t.on_flight(0.2) == 0
    assert t.on_flight(0.8) == 1
    assert t.value == 51.0


def test_prompt_default_and_override():
    """默认每档有提示词；配置 prompts 覆盖时优先生效；未知档位返回空串。"""
    for level in mood.MOOD_LEVELS:
        assert mood.mood_prompt(level)
    custom = MoodSettings(prompts={"happy": "自定义开心"})
    assert mood.mood_prompt("happy", custom) == "自定义开心"
    assert mood.mood_prompt("sad", custom) == mood.DEFAULT_PROMPTS["sad"]
    assert mood.mood_prompt("nonsense") == ""


def test_mood_image_name():
    """贴图命名为 {pet}-{mood}.png，如 kangel-angry.png。"""
    assert mood.mood_image_name("kangel", "angry") == "kangel-angry.png"
    assert mood.mood_image_name("ame", "happy") == "ame-happy.png"


def test_not_persisted_initial_value():
    """MoodTracker 新建时心情值恒为 initial（不持久化）。"""
    t = mood.MoodTracker(MoodSettings(initial=42.0))
    assert t.value == 42.0
    t.update(100.0)
    # 重新创建又回到 initial
    assert mood.MoodTracker(MoodSettings(initial=42.0)).value == 42.0

def test_click_counter_boosts_every_second_click():
    """每两次点击才加一次好感。"""
    counter = mood.ClickCounter(every=2, cooldown=0.0)
    assert counter.register(0.0) is False
    assert counter.count == 1
    assert counter.register(0.1) is True
    assert counter.count == 0


def test_click_counter_cooldown_blocks_boosts():
    """冷却期内点了也不加好感，冷却结束才恢复。"""
    counter = mood.ClickCounter(every=1, cooldown=0.4)
    assert counter.register(0.0) is True
    assert counter.cooldown_left(0.1) > 0
    assert counter.register(0.1) is False
    assert counter.count == 0
    assert counter.register(0.5) is True


def test_click_counter_remaining():
    counter = mood.ClickCounter(every=2)
    assert counter.remaining == 2
    counter.register(0.0)
    assert counter.remaining == 1


def test_practice_mode_freezes_at_100_and_restores():
    """直播练习：进入时钉在 100 且不衰减，退出恢复进入前的值。"""
    t = mood.MoodTracker(MoodSettings(initial=64.0))
    t.set_practice(True)
    assert t.practice is True
    assert t.value == 100.0
    t.update(60.0)  # 一分钟不衰减
    assert t.value == 100.0
    assert t.roll_pat() == 0  # 练习期间摸头也不涨（保持 100）
    t.on_drag(3.0)
    assert t.value == 100.0
    t.set_practice(False)
    assert t.practice is False
    assert math.isclose(t.value, 64.0)


def test_practice_mode_survives_multiple_toggles():
    """反复开关直播练习：每次都恢复到本次进入前的值。"""
    t = mood.MoodTracker(MoodSettings(initial=80.0))
    t.update(10.0)  # 79
    t.set_practice(True)
    t.set_practice(False)
    assert math.isclose(t.value, 79.0)
    t.set_practice(True)
    t.set_practice(False)
    assert math.isclose(t.value, 79.0)
