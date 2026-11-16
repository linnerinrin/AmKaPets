"""设置分组基类：统一的 QGroupBox 行/块排版。

用户口径（第四轮）：不再有「跟随全局」开关——所有配置只走实例设置，
所以本基类只负责「标签 + 控件」的排版与登记，不做任何启用状态联动。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .common import FIELD_MAX_W


class Section(QGroupBox):
    """一个设置分组：一行行「标签 + 控件」，也支持整块控件。"""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """构造分组。

        :param title: 分组标题（如「物理」「摸头」）。
        :param parent: Qt 父控件。
        """
        super().__init__(title, parent)
        self._fields: list[QWidget] = []
        self._rows_layout = QVBoxLayout(self)
        self._rows_layout.setSpacing(8)

    def add_row(self, label: str, *widgets: QWidget) -> None:
        """添加一行：标签 + 一到多个控件（按内容定宽，右侧留空）。"""
        row = QHBoxLayout()
        row.setSpacing(8)
        if label:
            row.addWidget(QLabel(label))
        for widget in widgets:
            if isinstance(widget, (QSpinBox, QDoubleSpinBox, QComboBox)):
                widget.setMaximumWidth(FIELD_MAX_W if not isinstance(widget, QComboBox) else 180)
            row.addWidget(widget)
            self._fields.append(widget)
        row.addStretch(1)
        self._rows_layout.addLayout(row)

    def add_block(self, label: str, widget: QWidget) -> None:
        """添加一整块：标签在上、控件独占整行宽（用于列表等长控件）。"""
        if label:
            self._rows_layout.addWidget(QLabel(label))
        self._rows_layout.addWidget(widget)
        self._fields.append(widget)


__all__ = ["Section"]
