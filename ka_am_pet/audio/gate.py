"""音乐模式闸门：持续播放够久才进入，短暂静音不退出（纯逻辑，禁 Qt，可单测）。"""

from __future__ import annotations

import random

# 音乐模式闸门参数：连续放够 20 秒才有机会进入，最迟 60 秒必定进入。
MUSIC_MIN_HOLD_SECONDS = 20.0
MUSIC_FULL_HOLD_SECONDS = 60.0
MUSIC_CHECK_SECONDS = 2.0     # 每隔 2 秒掷一次骰子（不逐帧判定，几乎不耗性能）
MUSIC_GRACE_SECONDS = 4.0     # 换歌/短暂静音不退出音乐模式


class MusicGate:
    """「持续播放够久才进入音乐模式」的闸门（纯逻辑，可单测）。

    解决「一有点声音就摇摆」的问题，同时保持低成本：
    - 连续播放时长 held < min_hold（默认 20s）时完全没有机会进入；
    - held 超过 min_hold 后，每 ``check_seconds`` 秒按概率 p 进入，
      ``p = (held - min_hold) / (full_hold - min_hold)`` 线性增长；
    - held 达到 full_hold（默认 60s）时 p=1，必定进入；
    - 音乐停下超过 grace 秒才退出；连续播放一旦中断，进入计时重新开始。
    """

    def __init__(
        self,
        min_hold: float = MUSIC_MIN_HOLD_SECONDS,
        full_hold: float = MUSIC_FULL_HOLD_SECONDS,
        check_seconds: float = MUSIC_CHECK_SECONDS,
        grace_seconds: float = MUSIC_GRACE_SECONDS,
        rng=None,
    ) -> None:
        """初始化闸门。

        :param min_hold: 进入音乐模式所需的最短连续播放秒数。
        :param full_hold: 必定进入音乐模式的最长连续播放秒数（须 >= min_hold）。
        :param check_seconds: 掷骰间隔（秒）。
        :param grace_seconds: 音乐停止多久后退出音乐模式。
        :param rng: 返回 [0,1) 的随机数函数（测试可注入）。
        """
        self._min_hold = max(0.0, float(min_hold))
        self._full_hold = max(self._min_hold, float(full_hold))
        self._check_seconds = max(0.1, float(check_seconds))
        self._grace_seconds = max(0.0, float(grace_seconds))
        self._random = rng or random.random
        self.active = False
        self._held = 0.0
        self._played_since: float | None = None
        self._quiet_since: float | None = None
        self._next_check = 0.0

    @property
    def held_seconds(self) -> float:
        """本轮连续播放已持续多少秒（未在播放时为 0）。"""
        return self._held

    def reset(self) -> None:
        """清空状态（停用音乐律动/实例重建时调用）。"""
        self.active = False
        self._held = 0.0
        self._played_since = None
        self._quiet_since = None
        self._next_check = 0.0

    def update(self, playing: bool, now: float) -> bool:
        """喂一次播放状态，返回当前是否处于音乐模式。

        :param playing: 音乐是否正在响（MusicReactor 的滞回结果）。
        :param now: 单调时钟（秒）。
        """
        if not playing:
            self._played_since = None
            self._held = 0.0
            if self.active:
                if self._quiet_since is None:
                    self._quiet_since = now
                elif now - self._quiet_since >= self._grace_seconds:
                    self.active = False
                    self._quiet_since = None
            return self.active

        self._quiet_since = None
        if self._played_since is None:
            self._played_since = now
            self._next_check = now + self._check_seconds
            return self.active  # 刚重新开始播放：本帧不判

        held = now - self._played_since
        self._held = held
        if self.active or now < self._next_check:
            return self.active
        self._next_check = now + self._check_seconds
        if held >= self._full_hold:
            self.active = True
        elif held >= self._min_hold:
            span = self._full_hold - self._min_hold
            chance = 0.0 if span <= 0 else (held - self._min_hold) / span
            if self._random() < chance:
                self.active = True
        return self.active
