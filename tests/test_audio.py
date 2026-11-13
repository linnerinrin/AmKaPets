"""音乐律动检测的纯逻辑测试（不触碰真实音频设备）。"""

from __future__ import annotations

from ka_am_pet.audio import MusicReactor


def test_silence_never_triggers():
    r = MusicReactor()
    for i in range(20):
        assert r.feed(0.0, i * 0.4) is False
    assert r.playing is False


def test_peak_starts_playing_and_fires_once_per_interval():
    r = MusicReactor(interval_seconds=1.5)
    assert r.feed(0.05, 0.0) is True          # 第一次超过门限立即触发
    assert r.feed(0.05, 0.4) is False         # 冷却中
    assert r.feed(0.05, 1.0) is False
    assert r.feed(0.05, 1.5) is True          # 到点再触发
    assert r.playing is True


def test_hysteresis_keeps_playing_on_quiet_dips():
    r = MusicReactor(quiet_frames=3, interval_seconds=100.0)
    assert r.feed(0.05, 0.0) is True
    # 短暂安静（低于 off 门限）不应立即判定停止
    assert r.feed(0.0, 1.0) is False
    assert r.playing is True
    assert r.feed(0.0, 2.0) is False
    assert r.feed(0.0, 3.0) is False          # 第 3 次安静才停
    assert r.playing is False


def test_mid_level_between_thresholds_keeps_state():
    r = MusicReactor()
    assert r.feed(0.05, 0.0) is True
    # 0.006 介于 off(0.004) 与 on(0.008) 之间：既不重开也不计安静
    assert r.playing is True
    r.feed(0.006, 0.5)
    r.feed(0.006, 1.0)
    r.feed(0.006, 1.5)
    assert r.playing is True


def test_none_peak_is_ignored():
    r = MusicReactor()
    assert r.feed(None, 0.0) is False
    assert r.playing is False
