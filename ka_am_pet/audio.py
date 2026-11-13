"""系统音频活动检测：Windows Core Audio 峰值表 + 音乐触发状态机（纯 Python，禁 Qt）。"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
import uuid
from ctypes import POINTER, Structure, byref, c_float, c_long, c_ubyte, c_uint, c_ulong, c_ushort, c_void_p

CLSCTX_ALL = 23
COINIT_MULTITHREADED = 0x0
EDataFlow_Render = 0
ERole_Console = 0

# 峰值门限的滞回：高于 on 值算"在响"，连续 quiet_frames 次低于 off 值才算安静
_ON_PEAK = 0.008
_OFF_PEAK = 0.004
_QUIET_FRAMES = 3

# 律动间隔（秒）范围：
#   下限 1.0 = 拉伸动画 0.2s + 飘字 0.8s，再快就会两段动画互相打断；
#   上限 10.0 = 再慢就不像"跟着音乐"，退化成偶尔动一下。
MIN_INTERVAL_SECONDS = 1.0
MAX_INTERVAL_SECONDS = 10.0
DEFAULT_INTERVAL_SECONDS = 1.5


def clamp_interval(seconds: float) -> float:
    """把律动间隔夹进 [MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS]。"""
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, float(seconds)))


class GUID(Structure):
    """Win32 GUID 结构（从 uuid 字符串构造）。"""

    _fields_ = [
        ("Data1", c_ulong),
        ("Data2", c_ushort),
        ("Data3", c_ushort),
        ("Data4", c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, text: str) -> "GUID":
        u = uuid.UUID(text)
        g = cls()
        g.Data1, g.Data2, g.Data3 = u.fields[0], u.fields[1], u.fields[2]
        for i, b in enumerate(u.bytes[8:]):
            g.Data4[i] = b
        return g


_CLSID_MM_DEVICE_ENUMERATOR = GUID.parse("BCDE0395-E52F-467C-8E3D-C4579291692E")
_IID_IMM_DEVICE_ENUMERATOR = GUID.parse("A95664D2-9614-4F35-A746-DE8DB63617E6")
_IID_IAUDIO_METER_INFORMATION = GUID.parse("C02216F6-8C67-4B5B-9D00-D008E73E0064")


def _vtbl_call(ptr: c_void_p, index: int, prototype):
    """调用 COM 对象 vtable 第 index 号方法。"""
    table = ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents
    return ctypes.cast(table[index], prototype)


def _release(ptr: c_void_p | None) -> None:
    if not ptr:
        return
    try:
        _vtbl_call(ptr, 2, ctypes.CFUNCTYPE(c_ulong, c_void_p))(ptr)
    except OSError:
        pass


class AudioPeakMeter:
    """默认输出设备的实时峰值（0.0–1.0），失败时 peak() 返回 None。

    只依赖系统自带 Core Audio，无需第三方库；线程内自建 COM 对象，
    调用方负责在同一个线程里用，不要在多个线程间共享。
    """

    def __init__(self) -> None:
        self._meter: c_void_p | None = None
        self._inited = False
        self._open()

    def _open(self) -> None:
        if sys.platform != "win32":
            return
        ole32 = ctypes.windll.ole32
        hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        # S_OK(0) 或 S_FALSE(1) 都表示本线程已初始化；RPC_E_CHANGED_MODE 也继续用
        self._inited = hr in (0, 1)
        enumerator = c_void_p()
        hr = ole32.CoCreateInstance(
            byref(_CLSID_MM_DEVICE_ENUMERATOR),
            None,
            CLSCTX_ALL,
            byref(_IID_IMM_DEVICE_ENUMERATOR),
            byref(enumerator),
        )
        if hr != 0 or not enumerator:
            return
        device = c_void_p()
        get_endpoint = _vtbl_call(
            enumerator,
            4,
            ctypes.CFUNCTYPE(c_long, c_void_p, c_uint, c_uint, POINTER(c_void_p)),
        )
        if get_endpoint(enumerator, EDataFlow_Render, ERole_Console, byref(device)) != 0 or not device:
            _release(enumerator)
            return
        meter = c_void_p()
        activate = _vtbl_call(
            device,
            3,
            ctypes.CFUNCTYPE(c_long, c_void_p, POINTER(GUID), c_ulong, c_void_p, POINTER(c_void_p)),
        )
        ok = activate(device, byref(_IID_IAUDIO_METER_INFORMATION), CLSCTX_ALL, None, byref(meter)) == 0
        _release(device)
        _release(enumerator)
        if ok and meter:
            self._meter = meter

    @property
    def available(self) -> bool:
        return self._meter is not None

    def peak(self) -> float | None:
        """读取当前输出峰值；对象不可用或调用失败返回 None。"""
        if self._meter is None:
            return None
        value = c_float(0.0)
        try:
            call = _vtbl_call(
                self._meter,
                3,
                ctypes.CFUNCTYPE(c_long, c_void_p, POINTER(c_float)),
            )
            if call(self._meter, byref(value)) != 0:
                return None
        except OSError:
            return None
        return float(value.value)

    def close(self) -> None:
        _release(self._meter)
        self._meter = None


class MusicReactor:
    """把峰值序列变成"是否该触发触摸动画"的纯逻辑状态机（可单测）。"""

    def __init__(
        self,
        on_peak: float = _ON_PEAK,
        off_peak: float = _OFF_PEAK,
        quiet_frames: int = _QUIET_FRAMES,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self._on_peak = on_peak
        self._off_peak = off_peak
        self._quiet_frames = quiet_frames
        self._interval = clamp_interval(interval_seconds)
        self._quiet_count = 0
        self._last_trigger: float | None = None
        self.playing = False

    @property
    def interval(self) -> float:
        """当前触发间隔（秒）。"""
        return self._interval

    def feed(self, peak: float | None, now: float) -> bool:
        """喂一次采样；返回 True 表示此刻应当触发一次触摸动画。"""
        if peak is None:
            return False
        if peak >= self._on_peak:
            self.playing = True
            self._quiet_count = 0
        elif peak <= self._off_peak:
            self._quiet_count += 1
            if self._quiet_count >= self._quiet_frames:
                self.playing = False
        if not self.playing:
            return False
        if self._last_trigger is None or now - self._last_trigger >= self._interval:
            self._last_trigger = now
            return True
        return False


class AudioWatcher(threading.Thread):
    """后台轮询系统输出峰值的守护线程（Qt 主线程只读 playing/peak）。"""

    def __init__(self, poll_seconds: float = 0.4, interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> None:
        super().__init__(daemon=True, name="audio-watcher")
        self._poll = poll_seconds
        self._stop = threading.Event()
        self._meter = AudioPeakMeter()
        self.reactor = MusicReactor(interval_seconds=interval_seconds)
        self.peak: float = 0.0
        self.triggered = False  # 主线程读取后自行复位

    @property
    def available(self) -> bool:
        return self._meter.available

    def run(self) -> None:
        while not self._stop.is_set():
            value = self._meter.peak()
            if value is not None:
                self.peak = value
                if self.reactor.feed(value, time.monotonic()):
                    self.triggered = True
            self._stop.wait(self._poll)

    def stop(self) -> None:
        self._stop.set()

    def take_trigger(self) -> bool:
        """取走一次触发标志（线程安全：单次赋值）。"""
        if self.triggered:
            self.triggered = False
            return True
        return False
