"""配置加载/保存健壮性测试。"""

import json

from ka_am_pet import config


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


def test_save_and_reload_roundtrip(tmp_path):
    """保存后能无损读回。"""
    path = tmp_path / "config.json"
    settings = config.default_config()
    settings.chat.api_key = "sk-test"
    settings.mood.prompts["happy"] = "嘿嘿"
    config.save_config(settings, path)
    loaded = config.load_config(path)
    assert loaded.chat.api_key == "sk-test"
    assert loaded.mood.prompts["happy"] == "嘿嘿"
    assert loaded.mode == settings.mode
