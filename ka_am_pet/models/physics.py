"""物理参数数据模型：甩抛与碰撞的全局/实例级参数（纯 dataclass，禁 Qt）。

默认值与取值范围见 AGENTS.md §5（gravity 1400 px/s²、restitution 0.78 等）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coercion import coerce_bool, coerce_float


@dataclass
class PhysicsParams:
    """甩抛与碰撞的物理参数。"""

    gravity: float = 1400.0
    restitution: float = 0.78
    ground_friction: float = 2.5
    ceiling_bounce: bool = True
    throw_power: float = 1.0
    pet_collision: bool = True

    @classmethod
    def from_dict(cls, raw: Any) -> "PhysicsParams":
        """从配置字典解析，字段级回退默认值。"""
        default = cls()
        if not isinstance(raw, dict):
            return default
        return cls(
            gravity=coerce_float(raw.get("gravity"), default.gravity, 0.0, 20000.0),
            restitution=coerce_float(raw.get("restitution"), default.restitution, 0.0, 1.0),
            ground_friction=coerce_float(raw.get("ground_friction"), default.ground_friction, 0.0, 100.0),
            ceiling_bounce=coerce_bool(raw.get("ceiling_bounce"), default.ceiling_bounce),
            throw_power=coerce_float(raw.get("throw_power"), default.throw_power, 0.0, 10.0),
            pet_collision=coerce_bool(raw.get("pet_collision"), default.pet_collision),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为配置字典。"""
        return {
            "gravity": self.gravity,
            "restitution": self.restitution,
            "ground_friction": self.ground_friction,
            "ceiling_bounce": self.ceiling_bounce,
            "throw_power": self.throw_power,
            "pet_collision": self.pet_collision,
        }
