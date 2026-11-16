"""音乐律动的纯逻辑状态机：峰值滞回判定 + 按实例的摇摆节拍（禁 Qt，可单测）。"""

from __future__ import annotations

# 峰值门限的滞回：高于 on 值算"在响"，连续 quiet_frames 次低于 off 值才算安静
_ON_PEAK = 0.008
_OFF_PEAK = 0.004
_QUIET_FRAMES = 3

# 律动间隔（秒）范围：
#   下限 0.5 = 约每秒两次摇摆（飘字允许重叠叠放，不会互相覆盖丢失）；
#   上限 10.0 = 再慢就不像"跟着音乐"，退化成偶尔动一下。
MIN_INTERVAL_SECONDS = 0.5
MAX_INTERVAL_SECONDS = 10.0
DEFAULT_INTERVAL_SECONDS = 1.5


def clamp_interval(seconds: float) -> float:
    """把律动间隔夹进 [MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS]。"""
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, float(seconds)))


class MusicReactor:
    """把峰值序列变成「音乐是否正在响」的纯逻辑状态机（滞回，可单测）。

    只负责判定播放状态；「多久摇摆一次」交给每只宠物自己的 SwayScheduler，
    这样全局只开一个音频线程，不同实例可以各自设置频率。
    """

    def __init__(
        self,
        on_peak: float = _ON_PEAK,
        off_peak: float = _OFF_PEAK,
        quiet_frames: int = _QUIET_FRAMES,
    ) -> None:
        self._on_peak = on_peak
        self._off_peak = off_peak
        self._quiet_frames = quiet_frames
        self._quiet_count = 0
        self.playing = False

    def feed(self, peak: float | None) -> bool:
        """喂一次采样，返回更新后的「是否正在播放」。

        :param peak: 当前输出峰值；None 表示读取失败（保持原状态）。
        """
        if peak is None:
            return self.playing
        if peak >= self._on_peak:
            self.playing = True
            self._quiet_count = 0
        elif peak <= self._off_peak:
            self._quiet_count += 1
            if self._quiet_count >= self._quiet_frames:
                self.playing = False
        return self.playing


class SwayScheduler:
    """按实例自己的间隔给音乐摇摆打节拍（纯逻辑，可单测）。

    - ``playing`` 为 False 时清空节拍，下一轮音乐开始时立刻先摇一下；
    - ``playing`` 为 True 时，每到间隔就触发一次。
    """

    def __init__(self, interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> None:
        self._interval = clamp_interval(interval_seconds)
        self._next_at: float | None = None

    @property
    def interval(self) -> float:
        """当前触发间隔（秒）。"""
        return self._interval

    def set_interval(self, seconds: float) -> None:
        """更新触发间隔（会被夹进合法范围）。"""
        self._interval = clamp_interval(seconds)

    def reset(self) -> None:
        """清空节拍（音乐停止、实例重建时调用）。"""
        self._next_at = None

    def should_fire(self, playing: bool, now: float) -> bool:
        """判断此刻是否该触发一次摇摆动作。

        :param playing: 音乐是否正在播放。
        :param now: 单调时钟（秒）。
        :return: True 表示此刻触发一次。
        """
        if not playing:
            self._next_at = None
            return False
        if self._next_at is not None and now < self._next_at:
            return False
        self._next_at = now + self._interval
        return True
