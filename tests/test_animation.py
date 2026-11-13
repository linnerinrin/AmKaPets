"""动画状态机测试。"""

import json

import pytest

from ka_am_pet.animation import AnimationManifest, AnimationStateMachine, load_manifest


def test_no_consecutive_repeat():
    """随机回应不连续重复上一段（多段可选时）。"""
    sm = AnimationStateMachine(idle="idle", reactions=["happy", "shy", "tsundere"])
    last = sm.on_click()
    for _ in range(200):
        chosen = sm.on_click()
        assert chosen != last, "不允许连续重复同一段回应"
        assert chosen in ("happy", "shy", "tsundere")
        last = chosen


def test_single_reaction_may_repeat():
    """只有一段回应时允许重复（例外规则）。"""
    sm = AnimationStateMachine(idle="idle", reactions=["happy"])
    assert sm.on_click() == "happy"
    assert sm.on_click() == "happy"


def test_reaction_returns_to_idle_after_finish():
    """非循环回应播完（按帧时长推进）后回到 idle。"""
    sm = AnimationStateMachine(idle="idle", reactions=["happy"])
    manifest = AnimationManifest(name="happy", fps=10.0, loop=False, frames=["1.png", "2.png"])
    sm.on_click()
    assert sm.update(0.1, manifest) == "happy"
    # 总时长 0.2s，推进到 0.21s 应回 idle
    assert sm.update(0.11, manifest) == "idle"


def test_idle_loops_forever():
    """idle 循环动画不会因时间推进而退出。"""
    sm = AnimationStateMachine(idle="idle", reactions=["happy"])
    idle_manifest = AnimationManifest(name="idle", fps=24.0, loop=True, frames=["1.png"])
    assert sm.update(999.0, idle_manifest) == "idle"


def test_load_manifest(tmp_path):
    """manifest.json 解析：正常、缺文件、字段非法。"""
    d = tmp_path / "happy"
    d.mkdir()
    (d / "manifest.json").write_text(
        json.dumps({"name": "happy", "fps": 24, "loop": False, "frames": ["001.png"], "width": 640, "height": 360}),
        encoding="utf-8",
    )
    m = load_manifest(d)
    assert m.name == "happy" and m.fps == 24.0 and not m.loop
    assert m.frame_duration == 1.0 / 24.0

    with pytest.raises(FileNotFoundError):
        load_manifest(tmp_path / "nothing")
    (d / "manifest.json").write_text(json.dumps({"name": "happy", "fps": -1, "frames": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(d)


def test_no_reactions_click_stays_idle():
    """无可用回应时点击保持 idle。"""
    sm = AnimationStateMachine(idle="idle", reactions=[])
    assert sm.on_click() == "idle"
