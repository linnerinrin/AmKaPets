"""历史会话分组：只读展示该实例的记忆，顶部显示总条数。

用户口径（第四轮）：聊天模块里要能看到「记忆中的上下文」，子模块名叫
「历史会话」，形式是只读列表——角色 + 时间 + 内容，顶部显示共 N 条。
数据直接来自 :class:`ka_am_pet.services.memory.MemoryStore`（全量保存）。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QWidget

from ...models import ChatMessage
from ...theme import Theme
from .base_section import Section

HISTORY_LIST_NAME = "chatHistoryList"
"""对象名：主题样式用 ID 选择器命中它（AGENTS.md §13.7）。"""

ROW_H = 24
MAX_ROWS = 7


def _row_text(message: ChatMessage) -> str:
    """一行展示文案：「你 · 10-31 20:15  内容」。"""
    who = "桌宠" if message.role == "assistant" else "你"
    stamp = datetime.fromtimestamp(message.ts).strftime("%m-%d %H:%M") if message.ts else "--"
    return f"{who} · {stamp}  {message.content}"


class ChatHistorySection(Section):
    """历史会话：只读列表 + 总条数（没有消息时给出空态文案）。"""

    def __init__(
        self,
        messages: Sequence[ChatMessage],
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """构造历史会话分组。

        :param messages: 该实例的全部历史消息（按时间升序）。
        :param theme: 界面主题；给了才给列表上色。
        :param parent: Qt 父控件。
        """
        super().__init__("历史会话", parent)
        self.count_label = QLabel(f"共 {len(messages)} 条")
        self.list = QListWidget()
        self.list.setObjectName(HISTORY_LIST_NAME)
        self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setFixedHeight(min(max(1, len(messages)), MAX_ROWS) * ROW_H + 10)
        if theme is not None:
            self.list.setStyleSheet(
                f"QListWidget#{HISTORY_LIST_NAME} {{"
                f" background: {theme.input_bg}; border: 1px solid {theme.border};"
                f" border-radius: 6px; padding: 4px; color: {theme.content_text}; }}"
            )
        if messages:
            for message in messages:
                self.list.addItem(QListWidgetItem(_row_text(message)))
        else:
            self.list.addItem(QListWidgetItem("（还没有对话记录）"))
        self.add_row("", self.count_label)
        self.add_block("", self.list)


__all__ = ["HISTORY_LIST_NAME", "ChatHistorySection"]
