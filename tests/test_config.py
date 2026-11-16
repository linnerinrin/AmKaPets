"""配置加载/保存健壮性测试。"""

import json

from ka_am_pet import actions, config
from ka_am_pet.models import DRAG_RANGE, FLIGHT_RANGE, MOOD_DECAY, PAT_RANGE


def test_default_config_generated_when_missing(tmp_path):
    """配置缺失时创建默认配置并落盘。"""
    path = tmp_path / "config.json"
    settings = config.load_config(path)
    assert settings.mode == "desktop"
    assert len(settings.pets) == 2  # 默认双宠：kangel + ame
    assert settings.pets[0].id == "kangel"
    assert settings.physics.gravity == 1400.0
    assert path.is_file(), "缺失时应写入默认配置"


def test_invalid_fields_fall_back_to_defaults(tmp_path):
    """字段非法时字段级回退默认值，不启动失败；未知字段保留。"""
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "mode": "banana",
                "physics": {"gravity": "很重", "restitution": 5.0},
                "pets": [{"id": "a", "size": "大"}, {"id": "a", "size": 300}],
                "chat": {"timeout_seconds": -3},
                "my_custom_field": {"keep": "me"},
            }
        ),
        encoding="utf-8",
    )
    settings = config.load_config(path)
    assert settings.mode == "desktop"
    assert settings.physics.gravity == 1400.0
    assert settings.physics.restitution == 1.0  # 钳制到合法范围
    assert settings.chat.timeout_seconds == 5  # 钳制到下限
    assert len(settings.pets) == 2
    assert settings.pets[0].size == 320  # 非法 size 回退
    assert settings.pets[1].id != settings.pets[0].id  # 重复 id 已修复
    # 未知字段保存后仍在
    config.save_config(settings, path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["my_custom_field"] == {"keep": "me"}


def test_corrupt_json_backed_up_and_rebuilt(tmp_path):
    """JSON 损坏：备份后重建默认配置，不崩溃。"""
    path = tmp_path / "config.json"
    path.write_text("{ 这不是 JSON", encoding="utf-8")
    settings = config.load_config(path)
    assert settings.mode == "desktop"
    backups = list(tmp_path.glob("config.corrupt-*.json"))
    assert backups, "损坏文件应被备份"
    assert path.is_file(), "应重建默认配置"


def test_audio_settings_default_and_clamped(tmp_path):
    """音乐律动：缺省开启、间隔 1.5s、动作池=全表；越界间隔被夹进 [0.5, 10.0]。"""
    path = tmp_path / "config.json"
    settings = config.load_config(path)
    assert settings.audio.enabled is True
    assert settings.audio.interval_seconds == 1.5
    assert set(settings.audio.music_pool) == set(actions.ACTIONS)

    path.write_text(json.dumps({"audio": {"enabled": False, "interval_seconds": 0.1}}), encoding="utf-8")
    settings = config.load_config(path)
    assert settings.audio.enabled is False
    assert settings.audio.interval_seconds == 0.5

    path.write_text(json.dumps({"audio": {"interval_seconds": 99}}), encoding="utf-8")
    assert config.load_config(path).audio.interval_seconds == 10.0

    # 动作池：多选按动作表顺序读入、未知项丢弃、空池回退全表
    path.write_text(json.dumps({"audio": {"music_pool": ["pat", "nod", "nope"]}}), encoding="utf-8")
    assert config.load_config(path).audio.music_pool == ("nod", "pat")
    path.write_text(json.dumps({"audio": {"music_pool": []}}), encoding="utf-8")
    assert set(config.load_config(path).audio.music_pool) == set(actions.ACTIONS)

    # 老配置（v4 及更早）只有单个 sway_mode：自动变成单元素动作池
    path.write_text(json.dumps({"audio": {"sway_mode": "sway"}}), encoding="utf-8")
    assert config.load_config(path).audio.music_pool == ("sway",)
    path.write_text(json.dumps({"audio": {"sway_mode": "旋转变身"}}), encoding="utf-8")
    assert set(config.load_config(path).audio.music_pool) == set(actions.ACTIONS)

    # 保存后能读回；好感数值是写死的常量，改内存值也不会被持久化
    settings = config.default_config()
    settings.audio.interval_seconds = 4.5
    settings.audio.enabled = False
    settings.audio.music_pool = ("sway",)
    settings.mood.decay_per_second = 1.5
    config.save_config(settings, path)
    loaded = config.load_config(path)
    assert (loaded.audio.enabled, loaded.audio.interval_seconds) == (False, 4.5)
    assert loaded.audio.music_pool == ("sway",)
    assert loaded.mood.decay_per_second == MOOD_DECAY


def test_mood_numbers_are_always_fixed_constants(tmp_path):
    """第四轮起好感数值全部写死：文件里写什么都不影响，一律回常量。"""
    path = tmp_path / "config.json"
    cases = (
        {"version": 4, "mood": {"decay_per_second": 0.5}},
        {"mood": {"decay_per_second": 0.5}},
        {"version": 4, "mood": {"decay_per_second": 1.5}},
        {"version": config.CONFIG_VERSION, "mood": {"decay_per_second": 0.5}},
    )
    for payload in cases:
        path.write_text(json.dumps(payload), encoding="utf-8")
        mood = config.load_config(path).mood
        assert mood.decay_per_second == MOOD_DECAY
        assert (mood.pat_min, mood.pat_max) == PAT_RANGE
        assert (mood.drag_min, mood.drag_max) == DRAG_RANGE
        assert (mood.flight_min, mood.flight_max) == FLIGHT_RANGE


def test_save_and_reload_roundtrip(tmp_path):
    """保存后能无损读回。"""
    path = tmp_path / "config.json"
    settings = config.default_config()
    settings.chat.api_key = "sk-test"
    settings.mood.prompts["happy"] = "嘿嘿"
    settings.theme = "custom:#112233/#ddeeff"
    settings.mood.pat_min, settings.mood.pat_max = -2, 3
    config.save_config(settings, path)
    loaded = config.load_config(path)
    assert loaded.chat.api_key == "sk-test"
    assert loaded.mood.prompts["happy"] == "嘿嘿"
    assert loaded.mode == settings.mode
    assert loaded.theme == "custom:#112233/#ddeeff"
    # 好感数值不持久化（写死）：读回来是常量
    assert (loaded.mood.pat_min, loaded.mood.pat_max) == PAT_RANGE


def test_theme_default_and_old_mood_keys_reset(tmp_path):
    """theme 缺省为 sky；旧版 click_boost/drag_boost/throw_boost 定值键与手写区间
    一律被忽略，全部回落写死的常量区间。"""
    import json

    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"mood": {"click_boost": 8, "drag_boost_per_second": 15, "throw_boost": 5}}),
        encoding="utf-8",
    )
    loaded = config.load_config(path)
    assert loaded.theme == "sky"
    assert (loaded.mood.pat_min, loaded.mood.pat_max) == PAT_RANGE
    assert (loaded.mood.drag_min, loaded.mood.drag_max) == DRAG_RANGE
    assert (loaded.mood.flight_min, loaded.mood.flight_max) == FLIGHT_RANGE

    # version=2 的旧配置同样回落常量
    path.write_text(
        json.dumps({"version": 2, "mood": {"click_boost": 8}}),
        encoding="utf-8",
    )
    assert config.load_config(path).mood.pat_min == PAT_RANGE[0]

    # 手写区间也不再生效（第四轮砍掉可编辑数值）
    path.write_text(
        json.dumps({"version": 2, "mood": {"click_boost": 8, "pat_min": -2, "pat_max": 3}}),
        encoding="utf-8",
    )
    loaded = config.load_config(path)
    assert (loaded.mood.pat_min, loaded.mood.pat_max) == PAT_RANGE


def test_drag_flight_defaults_are_zero_to_two(tmp_path):
    """好感区间全写死 [0,2]：建值、写文件、旧配置读入都是同一组常量。"""
    from ka_am_pet.models import MoodSettings

    defaults = MoodSettings()
    for pair in (
        (defaults.drag_min, defaults.drag_max),
        (defaults.flight_min, defaults.flight_max),
        (defaults.pat_min, defaults.pat_max),
    ):
        assert pair == (0, 2)

    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "version": 3,
                "mood": {"drag_min": -1, "drag_max": 1, "flight_min": -1, "flight_max": 1},
            }
        ),
        encoding="utf-8",
    )
    loaded = config.load_config(path)
    assert (loaded.mood.drag_min, loaded.mood.drag_max) == (0, 2)
    assert (loaded.mood.flight_min, loaded.mood.flight_max) == (0, 2)

    path.write_text(
        json.dumps({"version": 3, "mood": {"drag_min": -1, "drag_max": 3, "flight_min": 0, "flight_max": 1}}),
        encoding="utf-8",
    )
    loaded = config.load_config(path)
    assert (loaded.mood.drag_min, loaded.mood.drag_max) == (0, 2)
    assert (loaded.mood.flight_min, loaded.mood.flight_max) == (0, 2)
