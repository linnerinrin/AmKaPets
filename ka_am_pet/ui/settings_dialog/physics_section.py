"""物理参数设置分组：重力、弹性、摩擦、甩抛力度、碰撞开关。"""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel, QWidget

from ...models import PhysicsParams
from ..fields import DoubleSpinBox
from .base_section import Section


class PhysicsSection(Section):
    """物理参数：重力、弹性、摩擦、甩抛力度、碰撞开关（每实例独立）。"""

    def __init__(self, physics: PhysicsParams, parent: QWidget | None = None) -> None:
        """构造物理分组。

        :param physics: 该实例当前的物理参数（作为初值）。
        :param parent: Qt 父控件。
        """
        super().__init__("物理", parent)
        self.gravity = DoubleSpinBox()
        self.gravity.setRange(0.0, 20000.0)
        self.gravity.setSingleStep(100.0)
        self.gravity.setDecimals(0)
        self.gravity.setValue(physics.gravity)
        self.gravity.setSuffix(" px/s²")

        self.restitution = DoubleSpinBox()
        self.restitution.setRange(0.0, 1.0)
        self.restitution.setSingleStep(0.05)
        self.restitution.setDecimals(2)
        self.restitution.setValue(physics.restitution)

        self.friction = DoubleSpinBox()
        self.friction.setRange(0.0, 20.0)
        self.friction.setSingleStep(0.1)
        self.friction.setDecimals(2)
        self.friction.setValue(physics.ground_friction)
        self.friction.setSuffix(" /s")

        self.throw_power = DoubleSpinBox()
        self.throw_power.setRange(0.1, 3.0)
        self.throw_power.setSingleStep(0.1)
        self.throw_power.setDecimals(2)
        self.throw_power.setValue(physics.throw_power)
        self.throw_power.setSuffix(" ×")

        self.ceiling = QCheckBox("顶部反弹")
        self.ceiling.setChecked(physics.ceiling_bounce)
        self.collision = QCheckBox("多宠物碰撞")
        self.collision.setChecked(physics.pet_collision)

        self.add_row("重力", self.gravity, QLabel("弹性"), self.restitution)
        self.add_row("地面摩擦", self.friction, QLabel("甩抛力度"), self.throw_power)
        self.add_row("", self.ceiling, self.collision)

    def values(self) -> PhysicsParams:
        """读回物理参数。"""
        return PhysicsParams(
            gravity=float(self.gravity.value()),
            restitution=float(self.restitution.value()),
            ground_friction=float(self.friction.value()),
            ceiling_bounce=self.ceiling.isChecked(),
            throw_power=float(self.throw_power.value()),
            pet_collision=self.collision.isChecked(),
        )


__all__ = ["PhysicsSection"]
