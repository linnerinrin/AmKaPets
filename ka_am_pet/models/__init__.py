"""核心数据模型包：物理参数、宠物配置/状态、对话消息、实例覆盖与应用设置（纯 dataclass，禁 Qt）。

数据流一览：

- ``AppSettings`` 保存全局设置（config.json，只作为新建实例的默认值）。
- ``PetOverrides`` 保存单实例的完整设置组（物理 / 对话 / 律动），持久化在 SQLite。

包按职责拆分为多个子模块，本文件统一 re-export 原有公共名称，
保证 ``from ka_am_pet.models import X`` 的既有调用全部兼容。
"""

from .audio import AudioSettings
from .chat import ChatMessage, ChatOverrides, ChatSettings, effective_chat
from .coercion import coerce_bool, coerce_float, coerce_int, coerce_text
from .constants import ACTION_LABELS, MOOD_LEVELS, MUSIC_POOL
from .mood import (
    DRAG_RANGE,
    FLIGHT_RANGE,
    MOOD_DECAY,
    MOOD_INITIAL,
    PAT_RANGE,
    MoodSettings,
)
from .overrides import PetOverrides
from .pet import PetConfig, PetState
from .physics import PhysicsParams
from .settings import AppSettings

__all__ = [
    # 常量
    "MUSIC_POOL",
    "ACTION_LABELS",
    "MOOD_LEVELS",
    # 宽松解析工具
    "coerce_float",
    "coerce_int",
    "coerce_text",
    "coerce_bool",
    # 物理 / 宠物
    "PhysicsParams",
    "PetConfig",
    "PetState",
    # 对话
    "ChatMessage",
    "ChatSettings",
    "ChatOverrides",
    "effective_chat",
    # 心情 / 音乐
    "MoodSettings",
    "MOOD_INITIAL",
    "MOOD_DECAY",
    "PAT_RANGE",
    "DRAG_RANGE",
    "FLIGHT_RANGE",
    "AudioSettings",
    # 实例设置组
    "PetOverrides",
    # 应用设置
    "AppSettings",
]
