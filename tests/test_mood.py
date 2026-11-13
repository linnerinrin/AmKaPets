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
    t = mood.MoodTracker(MoodSettings(initial=80.0, click_boost=50.0))
    t.on_click()
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


def test_click_drag_throw_boosts():
    """点击 +click_boost；拖拽按秒增益；甩抛 +throw_boost。"""
    s = MoodSettings(initial=50.0, click_boost=8.0, drag_boost_per_second=15.0, throw_boost=5.0)
    t = mood.MoodTracker(s)
    t.on_click()
    assert math.isclose(t.value, 58.0)
    t.on_drag(2.0)
    assert math.isclose(t.value, 88.0)
    t.on_throw()
    assert math.isclose(t.value, 93.0)


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
