"""实例设置对话框：信息 / 聊天 / 交互三页，全部设置都按实例保存。

用户口径（第四轮）：
- 不再有「跟随全局」——每个实例都存完整配置（物理 / 对话 / 摇摆 / 摸头）。
- 信息页 = 基本行 + 「当前状态」卡片区（好感度进度条 + 直播练习按钮）。
- 聊天页 = 对话 API + 历史会话（只读记忆列表）。
- 交互页 = 物理 / 摸头 / 拖拽 / 飞行 / 摇摆 五个并列子模块。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from ...characters import BASE_CHARACTERS
from ...db import PetInstance
from ...models import ChatMessage, PetOverrides
from ...theme import theme_for
from ..fields import ComboBox, SpinBox
from ..layout import scroll, vbox
from ..sidebar import SidebarDialog
from .cards import MoodCard, StatusCardFrame
from .chat_history import ChatHistorySection
from .chat_section import ChatSection
from .common import FIELD_MAX_W
from .extra_sections import MusicSection
from .mood_sections import DragSection, FlightSection, PatSection
from .physics_section import PhysicsSection


class InstanceSettingsDialog(SidebarDialog):
    """单实例设置：三页 = 信息（含当前状态）/ 聊天（含历史会话）/ 交互（五模块）。"""

    practice_toggled = Signal(bool)

    def __init__(
        self,
        settings,  # noqa: ANN001（AppSettings，仅作新建实例的默认值）
        instance: PetInstance | None = None,
        mood_view: Mapping[str, object] | None = None,
        history: Sequence[ChatMessage] = (),
        parent: QWidget | None = None,
    ) -> None:
        """构造实例设置对话框。

        :param settings: 全局 AppSettings，只用来给新建实例提供默认值。
        :param instance: 待编辑实例；None 表示新建。
        :param mood_view: 当前状态数据（{"mood": {...}}），新建时可为空。
        :param history: 该实例的历史消息（用于「历史会话」只读列表）。
        """
        theme = theme_for(getattr(settings, "theme", "sky"))
        super().__init__("实例设置", theme, parent)
        self._settings = settings
        self._instance = instance
        overrides = instance.overrides if instance else PetOverrides(
            physics=settings.physics, chat=settings.chat, music=settings.audio
        )

        self._basic = _BasicWidget(instance)
        self.name_edit = self._basic.name_edit
        self.base_combo = self._basic.base_combo
        self.size_spin = self._basic.size_spin
        self.passthrough_check = self._basic.passthrough_check

        self.status_frame = StatusCardFrame()
        self.mood_card = MoodCard()
        self.mood_card.practice_toggled.connect(self.practice_toggled.emit)
        self.status_frame.add_card(self.mood_card)
        if mood_view:
            self.status_frame.refresh(mood_view)

        info = vbox(self._basic, self.status_frame)
        self.add_page("信息", scroll(info))

        # ---- 聊天：对话 API + 历史会话 ----
        self._chat = ChatSection(overrides.chat)
        self._history = ChatHistorySection(history, theme)
        self.add_page("聊天", scroll(vbox(self._chat, self._history)))

        # ---- 交互：物理 / 摸头 / 拖拽 / 飞行 / 摇摆 ----
        self._physics = PhysicsSection(overrides.physics)
        self._pat = PatSection(settings.mood, overrides.pat_pool, theme)
        self._drag = DragSection(settings.mood)
        self._flight = FlightSection(settings.mood)
        self._music = MusicSection(overrides.music, theme)
        self.add_page(
            "交互",
            scroll(vbox(self._physics, self._pat, self._drag, self._flight, self._music)),
        )

    def accept(self) -> None:  # noqa: D102（Qt 钩子）
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "名字不能为空", "给这只桌宠起个名字吧。")
            return
        super().accept()

    @property
    def result_instance(self) -> PetInstance:
        """把界面上的值回填成 PetInstance（新建实例 id 为空）。"""
        base_instance = self._instance
        chat = self._chat.values()
        overrides = PetOverrides(
            physics=self._physics.values(),
            chat=chat,
            music=self._music.values(),
            pat_pool=tuple(self._pat.pool_keys()) or PetOverrides().pat_pool,
        )
        return PetInstance(
            id=base_instance.id if base_instance else "",
            base=str(self.base_combo.currentData() or BASE_CHARACTERS[0][0]),
            name=self.name_edit.text().strip(),
            # 系统提示词同时写进 PetInstance 与 overrides.chat，兼容旧数据/旧记忆
            system_prompt=chat.system_prompt,
            size=int(self.size_spin.value()),
            x=base_instance.x if base_instance else None,
            y=base_instance.y if base_instance else None,
            created_ts=base_instance.created_ts if base_instance else 0.0,
            overrides=overrides,
            passthrough=self.passthrough_check.isChecked(),
        )


class _BasicWidget(QWidget):
    """信息页的基本行（桌宠类型 / 名字 / 大小 / 覆盖模式）。"""

    def __init__(self, instance: PetInstance | None, parent: QWidget | None = None) -> None:
        """构造基本行控件。"""
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.base_combo = ComboBox()
        for key, label in BASE_CHARACTERS:
            self.base_combo.addItem(label, key)
        base = instance.base if instance else BASE_CHARACTERS[0][0]
        if self.base_combo.findData(base) < 0:
            self.base_combo.addItem(base, base)
        self.base_combo.setCurrentIndex(self.base_combo.findData(base))
        self.base_combo.setEnabled(instance is None)  # 已有实例不改基底，避免贴图混乱
        self.name_edit = QLineEdit(instance.name if instance else "")
        self.name_edit.setMaxLength(24)
        self.size_spin = SpinBox()
        self.size_spin.setRange(120, 640)
        self.size_spin.setSingleStep(20)
        self.size_spin.setSuffix(" px")
        self.size_spin.setValue(int(instance.size if instance else 320))
        self.passthrough_check = QCheckBox("覆盖模式")
        self.passthrough_check.setChecked(bool(instance.passthrough) if instance else False)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(QLabel("桌宠类型"))
        self.base_combo.setMaximumWidth(180)
        top.addWidget(self.base_combo)
        top.addWidget(QLabel("名字"))
        self.name_edit.setMaximumWidth(160)
        top.addWidget(self.name_edit)
        top.addWidget(QLabel("大小"))
        self.size_spin.setMaximumWidth(FIELD_MAX_W)
        top.addWidget(self.size_spin)
        top.addStretch(1)
        layout.addRow(top)
        layout.addRow("", self.passthrough_check)


__all__ = ["InstanceSettingsDialog"]
