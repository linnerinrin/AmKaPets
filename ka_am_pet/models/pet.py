"""宠物配置与运行时状态数据模型（纯 dataclass，禁 Qt）。

坐标系约定：包围盒左上角，y 向下，速度 px/s（见 AGENTS.md §5）。
"""

from dataclasses import dataclass


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
    # 覆盖模式：只看得见、点不到；点击左上角眼睛按钮切换。
    passthrough: bool = False

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
