"""Windows Core Audio 峰值表：GUID/COM vtable 调用与 AudioPeakMeter（禁 Qt）。

只依赖系统自带 Core Audio，无需第三方库。线程内自建 COM 对象，
调用方负责在同一个线程里用，不要在多个线程间共享。
"""

from __future__ import annotations

import ctypes
import sys
import uuid
from ctypes import POINTER, Structure, byref, c_float, c_long, c_ubyte, c_uint, c_ulong, c_ushort, c_void_p

CLSCTX_ALL = 23
COINIT_MULTITHREADED = 0x0
EDataFlow_Render = 0
ERole_Console = 0


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
