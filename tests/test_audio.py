"""音乐律动检测的纯逻辑测试（不触碰真实音频设备）。"""

from __future__ import annotations

import random

from ka_am_pet.audio import (
    MUSIC_FULL_HOLD_SECONDS,
    MUSIC_MIN_HOLD_SECONDS,
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    MusicGate,
    MusicReactor,
    SwayScheduler,
    clamp_interval,
)


def test_silence_never_starts_playing():
    r = MusicReactor()
    for _ in range(20):
        assert r.feed(0.0) is False
    assert r.playing is False


def test_peak_starts_playing():
    r = MusicReactor()
    assert r.feed(0.05) is True
    assert r.playing is True


def test_hysteresis_keeps_playing_on_quiet_dips():
    r = MusicReactor(quiet_frames=3)
    assert r.feed(0.05) is True
    # 短暂安静（低于 off 门限）不应立即判定停止
    assert r.feed(0.0) is True
    assert r.feed(0.0) is True
    assert r.feed(0.0) is False          # 第 3 次安静才停
    assert r.playing is False


def test_mid_level_between_thresholds_keeps_state():
    r = MusicReactor()
    assert r.feed(0.05) is True
    # 0.006 介于 off(0.004) 与 on(0.008) 之间：既不重开也不计安静
    assert r.feed(0.006) is True
    assert r.feed(0.006) is True
    assert r.playing is True


def test_none_peak_is_ignored():
    r = MusicReactor()
    assert r.feed(None) is False
    assert r.feed(0.05) is True
    assert r.feed(None) is True          # 读取失败保持原状态
    assert r.playing is True


def test_interval_bounds_clamped():
    # 最快 0.5s（飘字可重叠叠放），最慢 10s
    assert (MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS) == (0.5, 10.0)
    assert clamp_interval(0.2) == 0.5
    assert clamp_interval(60) == 10.0
    assert clamp_interval(3.0) == 3.0


def test_sway_scheduler_fires_on_interval():
    scheduler = SwayScheduler(2.0)
    assert scheduler.should_fire(True, 0.0) is True    # 音乐一响立刻摇一下
    assert scheduler.should_fire(True, 1.0) is False
    assert scheduler.should_fire(True, 2.0) is True
    assert scheduler.should_fire(False, 3.0) is False  # 音乐停止：清空节拍
    assert scheduler.should_fire(True, 4.0) is True    # 再次开始：立刻摇


def test_sway_scheduler_interval_clamped():
    scheduler = SwayScheduler(0.01)
    assert scheduler.interval == MIN_INTERVAL_SECONDS
    scheduler.set_interval(99)
    assert scheduler.interval == MAX_INTERVAL_SECONDS
    scheduler.set_interval(3.0)
    assert scheduler.interval == 3.0

def test_music_gate_needs_sustained_playback():
    """默认 20s 内的一小段声音不会进入音乐模式。"""
    gate = MusicGate(rng=random.Random(3).random)
    now = 0.0
    for _ in range(10):  # 20 秒
        gate.update(True, now)
        now += 2.0
    assert MUSIC_MIN_HOLD_SECONDS == 20.0
    assert MUSIC_FULL_HOLD_SECONDS == 60.0
    assert gate.active is False


def test_music_gate_always_enters_after_full_hold():
    """连续播放满 60 秒必定进入（概率 p=1）。"""
    gate = MusicGate(rng=lambda: 0.999)
    now = 0.0
    gate.update(True, now)
    while now < MUSIC_FULL_HOLD_SECONDS:
        now += 2.0
        gate.update(True, now)
    assert gate.held_seconds >= MUSIC_FULL_HOLD_SECONDS
    assert gate.active is True


def test_music_gate_probability_grows():
    """中间阶段只在掷骰成功时进入：极小随机数也能在 min_hold 后进入。"""
    gate = MusicGate(rng=lambda: 0.0)
    now = 0.0
    gate.update(True, now)
    now = MUSIC_MIN_HOLD_SECONDS + 10.0
    assert gate.update(True, now) is True


def test_music_gate_leaves_after_grace():
    """音乐停下超过 grace 秒才退出；短暂静音保持音乐模式。"""
    gate = MusicGate(min_hold=2.0, full_hold=4.0, check_seconds=1.0, grace_seconds=4.0, rng=lambda: 0.0)
    now = 0.0
    gate.update(True, now)
    for _ in range(5):
        now += 1.0
        gate.update(True, now)
    assert gate.active is True
    gate.update(False, now + 0.1)
    assert gate.active is True          # grace 内
    gate.update(False, now + 5.0)
    assert gate.active is False


def test_music_gate_restart_resets_hold():
    """音乐中断后重新开始，计时清零（不能攒着算）。"""
    gate = MusicGate(rng=lambda: 0.0)
    now = 0.0
    gate.update(True, now)
    for _ in range(5):
        now += 2.0
        gate.update(True, now)
    gate.update(False, now + 0.5)
    now += 1.0
    gate.update(True, now)
    assert gate.held_seconds == 0.0


def test_music_gate_reset_clears_mode():
    gate = MusicGate(min_hold=2.0, full_hold=4.0, check_seconds=1.0, rng=lambda: 0.0)
    gate.update(True, 0.0)
    for t in (1.0, 2.0, 3.0, 4.0, 5.0):
        gate.update(True, t)
    assert gate.active is True
    gate.reset()
    assert gate.active is False
    assert gate.held_seconds == 0.0
