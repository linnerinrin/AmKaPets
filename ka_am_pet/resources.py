"""资源路径解析：源码运行与 PyInstaller 冻结运行双模式，以及用户可写数据目录。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    """返回只读资源根目录：源码=项目根（本文件上两级），冻结=sys._MEIPASS。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def asset_path(*parts: str) -> Path:
    """拼接资源根目录下的资源路径。

    :param parts: 资源相对路径的各段，如 "pets", "main", "idle"。
    :return: 资源绝对路径。
    """
    return resource_root().joinpath("assets", *parts)


def app_data_dir() -> Path:
    """返回 %APPDATA%\\ka-am-pet，不存在时自动创建。"""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    data_dir = root / "ka-am-pet"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
