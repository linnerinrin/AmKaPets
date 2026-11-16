"""回归测试：Qt 虚函数 mixin 的 MRO 顺序。

PetWidget 的 paintEvent/mousePressEvent 等 Qt 虚函数由 mixin 提供；
若 QWidget 排在 mixin 前面，QWidget 的空实现会按 MRO 遮蔽 mixin，
窗口不绘制、点击不响应（2026-11-15「宠物不可见」事故的根因）。
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ka_am_pet.ui.pet_widget.animation import PetAnimationMixin
from ka_am_pet.ui.pet_widget.interaction import PetInteractionMixin
from ka_am_pet.ui.pet_widget.rendering import PetRenderingMixin
from ka_am_pet.ui.pet_widget.widget import PetWidget


def test_mixin_virtuals_shadow_qwidget() -> None:
    """每个提供 Qt 虚函数的 mixin 在 MRO 中必须排在 QWidget 之前。"""
    order = PetWidget.mro()
    qwidget_index = order.index(QWidget)
    for mixin in (PetAnimationMixin, PetRenderingMixin, PetInteractionMixin):
        assert order.index(mixin) < qwidget_index, (
            f"{mixin.__name__} 必须排在 QWidget 之前，"
            "否则 paintEvent/mousePressEvent 会被 QWidget 空实现遮蔽"
        )


def test_paintevent_comes_from_mixin() -> None:
    """paintEvent 的实际实现必须来自渲染 mixin，而不是 QWidget。"""
    assert PetWidget.paintEvent is PetRenderingMixin.paintEvent
    assert PetWidget.mousePressEvent is PetInteractionMixin.mousePressEvent


def test_arrow_field_mixins_precede_qt_bases() -> None:
    """自绘箭头的 SpinBox/DoubleSpinBox：mixin 必须排在 Qt 基类之前。"""
    from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

    from ka_am_pet.ui.fields import _ArrowSpinMixin, DoubleSpinBox, SpinBox

    for cls, base in ((SpinBox, QSpinBox), (DoubleSpinBox, QDoubleSpinBox)):
        order = cls.mro()
        assert order.index(_ArrowSpinMixin) < order.index(base), (
            f"{cls.__name__}: _ArrowSpinMixin 必须排在 {base.__name__} 之前，"
            "否则 paintEvent/mousePressEvent 会被遮蔽"
        )
        assert cls.paintEvent is _ArrowSpinMixin.paintEvent


def test_chevron_combo_mixin_precedes_qt_base() -> None:
    """自绘下拉三角的 ComboBox：mixin 同样必须排在 QComboBox 之前。"""
    from PySide6.QtWidgets import QComboBox

    from ka_am_pet.ui.fields import ComboBox, _ChevronComboMixin

    order = ComboBox.mro()
    assert order.index(_ChevronComboMixin) < order.index(QComboBox)
    assert ComboBox.paintEvent is _ChevronComboMixin.paintEvent
