"""设置窗口：API 与物理/模式等配置编辑。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from ka_am_pet.models import AppSettings


class SettingsDialog(QDialog):
    """设置窗口：base_url / api_key / model / system_prompt / memory_rounds 等编辑保存。

    api_key 输入框使用密码显示；保存经 config.save_config 原子写回；
    API Key 不得写入日志。
    """

    settings_saved = Signal(object)  # AppSettings

    def __init__(self, settings: AppSettings, parent=None) -> None:
        """构造设置窗口。

        :param settings: 当前应用配置（用于回填表单）。
        :param parent: Qt 父控件。
        """
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("设置")
        self.resize(480, 480)

        chat = settings.chat
        self._base_url = QLineEdit(chat.base_url)
        self._api_key = QLineEdit(chat.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._model = QLineEdit(chat.model)
        self._system_prompt = QPlainTextEdit(chat.system_prompt)
        self._memory_rounds = QSpinBox()
        self._memory_rounds.setRange(1, 100)
        self._memory_rounds.setValue(chat.memory_rounds)
        self._timeout = QSpinBox()
        self._timeout.setRange(5, 300)
        self._timeout.setValue(chat.timeout_seconds)

        self._mode = QComboBox()
        self._mode.addItems(["desktop", "overlay"])
        self._mode.setCurrentText(settings.mode)

        self._gravity = QDoubleSpinBox()
        self._gravity.setRange(0, 10000)
        self._gravity.setValue(settings.physics.gravity)
        self._restitution = QDoubleSpinBox()
        self._restitution.setRange(0.0, 1.0)
        self._restitution.setSingleStep(0.01)
        self._restitution.setValue(settings.physics.restitution)
        self._throw_power = QDoubleSpinBox()
        self._throw_power.setRange(0.0, 10.0)
        self._throw_power.setSingleStep(0.1)
        self._throw_power.setValue(settings.physics.throw_power)

        form = QFormLayout()
        form.addRow("Base URL", self._base_url)
        form.addRow("API Key", self._api_key)
        form.addRow("模型", self._model)
        form.addRow("系统提示词", self._system_prompt)
        form.addRow("记忆轮数", self._memory_rounds)
        form.addRow("超时（秒）", self._timeout)
        form.addRow("运行模式", self._mode)
        form.addRow("重力", self._gravity)
        form.addRow("弹性系数", self._restitution)
        form.addRow("抛掷力度", self._throw_power)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_save(self) -> None:
        """回填 AppSettings 并发出保存信号（原子写由调用方做）。"""
        s = self._settings
        s.chat.base_url = self._base_url.text().strip().rstrip("/") or s.chat.base_url
        s.chat.api_key = self._api_key.text().strip()
        s.chat.model = self._model.text().strip() or s.chat.model
        s.chat.system_prompt = self._system_prompt.toPlainText()
        s.chat.memory_rounds = self._memory_rounds.value()
        s.chat.timeout_seconds = self._timeout.value()
        s.mode = self._mode.currentText()
        s.physics.gravity = self._gravity.value()
        s.physics.restitution = self._restitution.value()
        s.physics.throw_power = self._throw_power.value()
        self.settings_saved.emit(s)
        self.accept()
