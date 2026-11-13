"""核心数据模型：物理参数、宠物配置/状态、对话消息与应用设置（纯 dataclass，禁 Qt）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PhysicsParams:
    """甩抛与碰撞的物理参数。"""

    gravity: float = 1400.0
    restitution: float = 0.78
    ground_friction: float = 2.5
    ceiling_bounce: bool = True
    throw_power: float = 1.0
    pet_collision: bool = True


@dataclass
class PetConfig:
    """单只宠物的配置项。x/y 为 None 表示使用默认位置。

    base 是基底角色 id（assets/pets/<base>/ 贴图目录）；system_prompt 为该
    实例的独立人格提示词，为空时用全局 ChatSettings.system_prompt。
    """

    id: str
    name: str
    size: int
    x: float | None = None
    y: float | None = None
    base: str = ""
    system_prompt: str = ""


@dataclass
class PetState:
    """单只宠物的运行时状态（坐标为包围盒左上角，y 向下，速度 px/s）。"""

    pet_id: str
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    size: int = 320
    flying: bool = False
    dragging: bool = False
    current_animation: str = "idle"

    @property
    def width(self) -> int:
        """宠物包围盒宽度（px），等于 size。"""
        return self.size

    @property
    def height(self) -> int:
        """宠物包围盒高度（px），按 16:9 由 size 推导。"""
        return self.size * 9 // 16

    @property
    def rect(self) -> tuple[float, float, float, float]:
        """宠物包围盒矩形，返回 (x, y, width, height)。"""
        return (self.x, self.y, float(self.width), float(self.height))


@dataclass
class ChatMessage:
    """一条对话消息：role / content / ts（Unix 秒）。"""

    role: str
    content: str
    ts: float


@dataclass
class ChatSettings:
    """OpenAI 兼容 Chat Completions 的设置。"""

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    system_prompt: str = "你是桌面上的可爱桌宠，回答自然简短。"
    memory_rounds: int = 5
    timeout_seconds: int = 45


@dataclass
class MoodSettings:
    """心情系统设置（数值见 AGENTS.md §6.5）。prompts 非空项覆盖默认提示词。"""

    initial: float = 80.0
    decay_per_second: float = 0.1
    click_boost: float = 8.0
    drag_boost_per_second: float = 15.0
    throw_boost: float = 5.0
    prompts: dict[str, str] = field(default_factory=dict)


@dataclass
class AppSettings:
    """应用整体设置。"""

    mode: str = "desktop"
    physics: PhysicsParams = field(default_factory=PhysicsParams)
    pets: list[PetConfig] = field(default_factory=list)
    chat: ChatSettings = field(default_factory=ChatSettings)
    mood: MoodSettings = field(default_factory=MoodSettings)
