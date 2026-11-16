"""后台音频轮询线程：读峰值、喂状态机、更新音乐模式（禁 Qt）。"""

from __future__ import annotations

import threading
import time

from .gate import MusicGate
from .logic import MusicReactor
from .meter import AudioPeakMeter


class AudioWatcher(threading.Thread):
    """后台轮询系统输出峰值的守护线程（Qt 主线程只读 playing/music_mode/peak）。"""

    def __init__(self, poll_seconds: float = 0.4) -> None:
        super().__init__(daemon=True, name="audio-watcher")
        self._poll = poll_seconds
        self._stop = threading.Event()
        self._meter = AudioPeakMeter()
        self.reactor = MusicReactor()
        self.gate = MusicGate()
        self.peak: float = 0.0
        self._music_mode = False

    @property
    def available(self) -> bool:
        """音频峰值表是否可用。"""
        return self._meter.available

    @property
    def playing(self) -> bool:
        """当前是否有声音在响（原始滞回结果）。"""
        return self.reactor.playing

    @property
    def music_mode(self) -> bool:
        """是否已进入「音乐模式」（持续播放够久后的稳定状态）。"""
        return self._music_mode

    def run(self) -> None:
        while not self._stop.is_set():
            value = self._meter.peak()
            if value is not None:
                self.peak = value
                self.reactor.feed(value)
            self._music_mode = self.gate.update(self.reactor.playing, time.monotonic())
            self._stop.wait(self._poll)

    def stop(self) -> None:
        self._stop.set()
