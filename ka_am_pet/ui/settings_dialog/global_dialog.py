"""UI 设置对话框：整机范围的少数设置（运行模式 / 覆盖层透明度 / 主题色）。

用户口径（第四轮）：原来的「全局设置」整块取消——物理、对话、摇摆、摸头
等所有配置都只走实例设置；这里只保留真正属于整机的三项外观/形态设置，
并且从托盘菜单以「UI 设置」的名字进入。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QWidget

from ...theme import theme_for
from ..fields import ComboBox, DoubleSpinBox
from ..layout import scroll, vbox
from ..sidebar import SidebarDialog
from .common import FIELD_MAX_W, MODE_LABELS
from .extra_sections import ThemeSection


class SettingsDialog(SidebarDialog):
    """UI 设置：运行模式 + 覆盖模式透明度 + 主题色。"""

    settings_saved = Signal(object)

    def __init__(self, settings, parent: QWidget | None = None) -> None:  # noqa: ANN001
        """构造 UI 设置对话框。

        :param settings: 当前 AppSettings（保存时只更新这三项）。
        """
        theme = theme_for(getattr(settings, "theme", "sky"))
        super().__init__("UI 设置", theme, parent)
        self._settings = settings

        info = QWidget()
        info_layout = QFormLayout(info)
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._mode = ComboBox()
        for key, label in MODE_LABELS.items():
            self._mode.addItem(label, key)
        mode_index = self._mode.findData(settings.mode)
        if mode_index >= 0:
            self._mode.setCurrentIndex(mode_index)
        self._opacity = DoubleSpinBox()
        self._opacity.setRange(0.2, 1.0)
        self._opacity.setSingleStep(0.05)
        self._opacity.setDecimals(2)
        self._opacity.setValue(float(getattr(settings, "overlay_opacity", 0.92)))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("运行模式"))
        self._mode.setMaximumWidth(160)
        row.addWidget(self._mode)
        row.addWidget(QLabel("覆盖模式透明度"))
        self._opacity.setMaximumWidth(FIELD_MAX_W)
        row.addWidget(self._opacity)
        row.addStretch(1)
        info_layout.addRow(row)
        # 命名红线：不能叫 self._theme——ThemedDialog.theme 属性返回 Theme 对象，
        # 同名属性会被分组控件顶掉（曾经的表现：打开设置直接 AttributeError）
        self._theme_section = ThemeSection(getattr(settings, "theme", "sky"))
        self.add_page("外观", scroll(vbox(info, self._theme_section)))

    def accept(self) -> None:  # noqa: D102（Qt 钩子）
        settings = self._settings
        settings.mode = str(self._mode.currentData() or "desktop")
        settings.overlay_opacity = float(self._opacity.value())
        settings.theme = self._theme_section.theme_key()
        self.settings_saved.emit(settings)
        super().accept()


__all__ = ["SettingsDialog"]
