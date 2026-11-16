"""宽松解析工具：配置/数据库里的脏值一律回退默认值，不让启动失败。

所有 coerce_* 函数对 bool 特殊处理（bool 是 int 子类，但配置语义上
``true`` 不等于数字 1），并对 NaN 显式回退。
"""

from typing import Any


def coerce_float(value: Any, default: float, lo: float | None = None, hi: float | None = None) -> float:
    """把任意值解析成 float；非法值回退 default，并可按 [lo, hi] 钳制。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    result = float(value)
    if result != result:  # NaN
        return default
    if lo is not None:
        result = max(lo, result)
    if hi is not None:
        result = min(hi, result)
    return result


def coerce_int(value: Any, default: int, lo: int | None = None, hi: int | None = None) -> int:
    """把任意值解析成 int；非法值回退 default，并可按 [lo, hi] 钳制。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    result = int(value)
    if lo is not None:
        result = max(lo, result)
    if hi is not None:
        result = min(hi, result)
    return result


def coerce_text(value: Any, default: str, allow_empty: bool = False) -> str:
    """把任意值解析成字符串；非字符串或（默认）空串回退 default。"""
    if not isinstance(value, str):
        return default
    if not allow_empty and not value.strip():
        return default
    return value


def coerce_bool(value: Any, default: bool) -> bool:
    """只接受真正的 bool，其它类型回退 default。"""
    return value if isinstance(value, bool) else default
