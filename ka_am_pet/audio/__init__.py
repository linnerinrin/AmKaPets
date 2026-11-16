"""系统音频活动检测包：Windows Core Audio 峰值表 + 音乐播放判定/摇摆节拍（纯 Python，禁 Qt）。

对外接口与原 ``ka_am_pet.audio`` 单文件模块完全一致，既有调用不破。

子模块职责：
- :mod:`.meter`    —— Win32 COM/GUID 与 AudioPeakMeter（平台相关）；
- :mod:`.logic`    —— 峰值滞回判定（MusicReactor）与摇摆节拍（SwayScheduler）；
- :mod:`.gate`     —— 音乐模式闸门（MusicGate 与 MUSIC_* 常量）；
- :mod:`.watcher`  —— 后台轮询线程 AudioWatcher。
"""

from .gate import (
    MUSIC_CHECK_SECONDS,
    MUSIC_FULL_HOLD_SECONDS,
    MUSIC_GRACE_SECONDS,
    MUSIC_MIN_HOLD_SECONDS,
    MusicGate,
)
from .logic import (
    DEFAULT_INTERVAL_SECONDS,
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    MusicReactor,
    SwayScheduler,
    clamp_interval,
)
from .meter import AudioPeakMeter, GUID
from .watcher import AudioWatcher

__all__ = [
    "AudioPeakMeter",
    "AudioWatcher",
    "DEFAULT_INTERVAL_SECONDS",
    "GUID",
    "MAX_INTERVAL_SECONDS",
    "MIN_INTERVAL_SECONDS",
    "MUSIC_CHECK_SECONDS",
    "MUSIC_FULL_HOLD_SECONDS",
    "MUSIC_GRACE_SECONDS",
    "MUSIC_MIN_HOLD_SECONDS",
    "MusicGate",
    "MusicReactor",
    "SwayScheduler",
    "clamp_interval",
]
