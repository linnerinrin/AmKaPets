"""动画状态机测试。"""

import json
import types

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


class _PlayStub:
    """伪 PetWidget：只提供 play_action 用到的几个属性/方法（不碰 Qt）。"""

    def __init__(self):
        self._popups = []
        self._stretch_kind = None
        self.flip_runs = 0

    def _start_flip_run(self, flips):
        self.flip_runs += flips

    def _push_popup(self, text):
        self._popups.append(text)

    def update(self):
        pass


def test_play_action_accepts_spec_without_falling_back_to_nod():
    """play_action 传 ActionSpec 时必须播该动作，不能静默回退成点头摇摆。

    回归点：actions 的随机/映射函数返回的是 ActionSpec；早期 play_action 只认 key，
    `ACTIONS.get(spec)` 恒为 None → 无论设置成什么动作都只会点头。
    """
    from ka_am_pet import actions
    from ka_am_pet.ui.pet_widget.animation import PetAnimationMixin

    stub = _PlayStub()
    PetAnimationMixin.play_action(stub, actions.action("sway"))
    assert stub.flip_runs == 2, "左右摇摆应走翻转分支（flips=2）"
    assert stub._stretch_kind is None

    stub = _PlayStub()
    PetAnimationMixin.play_action(stub, actions.action("pat"))
    assert stub._stretch_kind == "squish", "摸头应走压扁分支，而不是回退成点头的 stretch"

    stub = _PlayStub()
    PetAnimationMixin.play_action(stub, "pat")  # 传 key 也要照常工作
    assert stub._stretch_kind == "squish"


class _MusicWorld:
    """伪 PetWorld：只为 music 路径提供 audio_for。"""

    def __init__(self, pool):
        self.audio = types.SimpleNamespace(music_pool=pool)

    def audio_for(self, pet_id):  # noqa: ARG002（测试桩，忽略参数）
        """返回预设的音乐设置。"""
        return self.audio


def test_music_reaction_only_plays_pool_actions():
    """听歌摇摆只在设置的动作池里随机，池外的动作不会播（第三轮需求）。"""
    from ka_am_pet.ui.pet_widget.animation import PetAnimationMixin

    played: list[str] = []
    stub = types.SimpleNamespace(
        _world=_MusicWorld(("sway",)),
        _pet_cfg=types.SimpleNamespace(id="kangel"),
        play_action=lambda spec, with_popup=None: played.append(spec.key),
    )
    for _ in range(20):
        PetAnimationMixin.play_music_reaction(stub)
    assert len(played) == 20  # 每次都会播
    assert set(played) == {"sway"}  # 且只播池里勾选的那个

