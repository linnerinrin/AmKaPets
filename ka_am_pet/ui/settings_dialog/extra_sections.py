"""音乐律动与主题色设置分组。

- :class:`MusicSection`：每实例独立的「是否律动 / 间隔 / 摇摆动作池」。
- :class:`ThemeSection`：整机主题色（只在「UI 设置」里出现）。
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QLabel,
    QPushButton,
    QWidget,
)

from ...actions import clean_pool
from ...models import MUSIC_POOL, AudioSettings
from ...theme import THEMES, Theme, custom_key, theme_for
from ..fields import ComboBox, DoubleSpinBox
from .pool import ActionPool
from .base_section import Section
from .common import CUSTOM_THEME


class MusicSection(Section):
    """音乐律动：开关（用户口径里的「是否律动」）、间隔、摇摆动作池。"""

    def __init__(
        self,
        audio: AudioSettings,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """构造音乐分组。

        :param audio: 该实例当前的音乐设置（作为初值）。
        :param theme: 界面主题；给了才给动作池列表上色。
        :param parent: Qt 父控件。
        """
        super().__init__("摇摆", parent)
        self.enabled = QCheckBox("启用")
        self.enabled.setChecked(audio.enabled)
        self.interval = DoubleSpinBox()
        self.interval.setRange(0.5, 10.0)
        self.interval.setSingleStep(0.5)
        self.interval.setDecimals(1)
        self.interval.setValue(audio.interval_seconds)
        self.interval.setSuffix(" 秒")
        checked = clean_pool(audio.music_pool) or MUSIC_POOL
        self.pool = ActionPool(MUSIC_POOL, checked, theme)

        self.add_row("", self.enabled, QLabel("摇摆间隔"), self.interval)
        self.add_block("摇摆动作（勾选的动作会被随机播放，可多选）", self.pool)

    def values(self) -> AudioSettings:
        """读回音乐设置；一个都没勾时回退成全表（等于「每个动作都可能播」）。"""
        return AudioSettings(
            enabled=self.enabled.isChecked(),
            interval_seconds=float(self.interval.value()),
            music_pool=clean_pool(self.pool.checked_keys()) or MUSIC_POOL,
        )


class ThemeSection(Section):
    """主题色：预设主题或自定义两个颜色（1=导航/进度条/气泡，2=内容主色）。"""

    def __init__(self, theme_key: str, parent: QWidget | None = None) -> None:
        """构造主题分组。

        :param theme_key: 当前配置里的主题 key（"sky" 或 "custom:#c1/#c2"）。
        """
        super().__init__("主题", parent)
        current = theme_for(theme_key)
        self.preset = ComboBox()
        for key, item in THEMES.items():
            self.preset.addItem(item.label, key)
        self.preset.addItem("自定义…", CUSTOM_THEME)
        index = self.preset.findData(current.key if current.key in THEMES else CUSTOM_THEME)
        if index >= 0:
            self.preset.setCurrentIndex(index)
        self._color1 = current.color1
        self._color2 = current.color2
        self.swatch1 = QPushButton()
        self.swatch2 = QPushButton()
        for swatch in (self.swatch1, self.swatch2):
            swatch.setFixedSize(26, 22)
        self.swatch1.clicked.connect(lambda: self._pick(1))
        self.swatch2.clicked.connect(lambda: self._pick(2))
        self._sync_swatches()
        self.preset.currentIndexChanged.connect(self._on_preset_changed)
        self._on_preset_changed()
        self.add_row("主题色", self.preset, self.swatch1, self.swatch2)

    def _sync_swatches(self) -> None:
        """把两个色块刷成当前自定义色。"""
        self.swatch1.setStyleSheet(f"background:{self._color1};border:1px solid #aab;border-radius:4px;")
        self.swatch2.setStyleSheet(f"background:{self._color2};border:1px solid #aab;border-radius:4px;")

    def _pick(self, which: int) -> None:
        """弹颜色选择器改自定义色。"""
        initial = QColor(self._color1 if which == 1 else self._color2)
        color = QColorDialog.getColor(initial, self, "主题色1" if which == 1 else "主题色2")
        if not color.isValid():
            return
        if which == 1:
            self._color1 = color.name()
        else:
            self._color2 = color.name()
        self._sync_swatches()

    def _on_preset_changed(self) -> None:
        """预设切换：自定义时启用两个色块。"""
        custom = self.preset.currentData() == CUSTOM_THEME
        self.swatch1.setEnabled(custom)
        self.swatch2.setEnabled(custom)

    def theme_key(self) -> str:
        """读回主题 key（预设 key 或 custom:#c1/#c2）。"""
        data = str(self.preset.currentData() or "sky")
        if data == CUSTOM_THEME:
            return custom_key(self._color1, self._color2)
        return data


__all__ = ["MusicSection", "ThemeSection"]
