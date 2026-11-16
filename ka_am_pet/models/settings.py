"""应用整体设置数据模型（纯 dataclass，禁 Qt）。

AppSettings 对应 config.json 的根结构；字段级解析逻辑在 config.py，
本模块只声明数据结构。
"""

from dataclasses import dataclass, field

from .audio import AudioSettings
from .chat import ChatSettings
from .mood import MoodSettings
from .pet import PetConfig
from .physics import PhysicsParams


@dataclass
class AppSettings:
    """应用整体设置。

    overlay_opacity 是 overlay 模式整层的不透明度（0.3-1.0）：overlay 是一整块置顶
    覆盖层，调低它能让桌宠更「融进」桌面，不挡视线；desktop 模式每只宠物独立窗口，
    不套用这个值（窗口透明度单独由 QA 决定，避免误伤）。
    """

    mode: str = "desktop"
    physics: PhysicsParams = field(default_factory=PhysicsParams)
    pets: list[PetConfig] = field(default_factory=list)
    chat: ChatSettings = field(default_factory=ChatSettings)
    mood: MoodSettings = field(default_factory=MoodSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    overlay_opacity: float = 0.92
    theme: str = "sky"
    """界面主题 key（见 theme.THEMES，默认淡蓝/白）；另可存 "custom:#c1/#c2" 自定义两色。"""
