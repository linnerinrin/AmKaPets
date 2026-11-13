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
class ChatOverrides:
    """单个实例的对话 API 覆盖项：空串 / 0 表示「继承全局设置」。"""

    base_url: str = ""
    api_key: str = ""
    model: str = ""
    memory_rounds: int = 0
    timeout_seconds: int = 0

    def is_empty(self) -> bool:
        """没有任何覆盖项（全部继承全局）时返回 True。"""
        return not (
            self.base_url
            or self.api_key
            or self.model
            or self.memory_rounds
            or self.timeout_seconds
        )


def effective_chat(
    global_chat: ChatSettings,
    overrides: ChatOverrides | None = None,
    instance_prompt: str = "",
    mood_prompt: str = "",
) -> ChatSettings:
    """把全局对话设置 + 实例覆盖 + 实例人格/心情提示词合成一份新设置。

    :param global_chat: 全局 ChatSettings（缺省值的来源）。
    :param overrides: 实例级覆盖项（None 或全空 = 完全继承）。
    :param instance_prompt: 实例独立人格提示词（空则用全局 system_prompt）。
    :param mood_prompt: 心情提示词（非空则追加到系统提示词末尾）。
    :return: 合并后的新 ChatSettings（不修改入参）。
    """
    ov = overrides or ChatOverrides()
    prompt = instance_prompt.strip() or global_chat.system_prompt
    if mood_prompt.strip():
        prompt = f"{prompt}\n{mood_prompt.strip()}"
    return ChatSettings(
        base_url=(ov.base_url or global_chat.base_url).rstrip("/"),
        api_key=ov.api_key or global_chat.api_key,
        model=ov.model or global_chat.model,
        system_prompt=prompt,
        memory_rounds=ov.memory_rounds or global_chat.memory_rounds,
        timeout_seconds=ov.timeout_seconds or global_chat.timeout_seconds,
    )


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
class AudioSettings:
    """音乐律动设置：开关 + 触发间隔（秒）。间隔范围见 audio.MIN/MAX_INTERVAL_SECONDS。"""

    enabled: bool = True
    interval_seconds: float = 1.5


@dataclass
class AppSettings:
    """应用整体设置。"""

    mode: str = "desktop"
    physics: PhysicsParams = field(default_factory=PhysicsParams)
    pets: list[PetConfig] = field(default_factory=list)
    chat: ChatSettings = field(default_factory=ChatSettings)
    mood: MoodSettings = field(default_factory=MoodSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
