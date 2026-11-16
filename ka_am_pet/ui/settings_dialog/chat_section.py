"""对话 API 设置分组：每实例的完整 ChatSettings（含系统提示词）。"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from ...models import ChatSettings
from ..fields import SpinBox
from .base_section import Section


class ChatSection(Section):
    """对话 API 设置：地址 / Key / 模型 / 系统提示词 / 记忆轮数 / 超时。

    用户口径（第四轮）：不再有「跟随全局」——每个实例都保存完整设置，
    原先信息页的「独立提示词」也并入这里的系统提示词。
    """

    def __init__(self, chat: ChatSettings, parent: QWidget | None = None) -> None:
        """构造聊天 API 分组。

        :param chat: 该实例当前的对话设置（作为初值）。
        :param parent: Qt 父控件。
        """
        super().__init__("对话 API", parent)

        self.base_url = QLineEdit(chat.base_url)
        self.api_key = QLineEdit(chat.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.model = QLineEdit(chat.model)
        self.system_prompt = QLineEdit(chat.system_prompt)
        self.system_prompt.setPlaceholderText("这只桌宠的人格设定")
        self.memory_rounds = SpinBox()
        self.memory_rounds.setRange(1, 100)
        self.memory_rounds.setValue(int(chat.memory_rounds))
        self.memory_rounds.setSuffix(" 轮")
        self.timeout = SpinBox()
        self.timeout.setRange(5, 300)
        self.timeout.setValue(int(chat.timeout_seconds))
        self.timeout.setSuffix(" 秒")

        self.add_row("Base URL", self.base_url)
        self.add_row("API Key", self.api_key)
        self.add_row("模型", self.model)
        self.add_row("系统提示词", self.system_prompt)
        self.add_row("记忆轮数", self.memory_rounds, QLabel("超时"), self.timeout)

    def values(self) -> ChatSettings:
        """读回完整对话设置（空地址/模型回退到入参值，避免写坏配置）。"""
        return ChatSettings(
            base_url=self.base_url.text().strip() or "https://api.openai.com/v1",
            api_key=self.api_key.text().strip(),
            model=self.model.text().strip() or "gpt-4o-mini",
            system_prompt=self.system_prompt.text().strip() or ChatSettings().system_prompt,
            memory_rounds=max(1, int(self.memory_rounds.value())),
            timeout_seconds=max(5, int(self.timeout.value())),
        )


__all__ = ["ChatSection"]
