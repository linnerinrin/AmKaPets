"""对话窗口：OpenAI 兼容 Chat Completions 对话 UI。"""

from __future__ import annotations

import threading

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from ka_am_pet.models import ChatSettings
from ka_am_pet.services.memory import MemoryStore
from ka_am_pet.services.openai_chat import ChatError, ChatService


class ChatDialog(QDialog):
    """宠物对话窗口：输入框/发送按钮/消息列表。

    请求期间禁用发送按钮并显示"思考中…"，结束后恢复；网络请求在 worker
    线程执行，结果经 Qt Signal 回主线程；错误以中文显示在窗口内；
    未配置 API Key 时提示去设置填写，不影响其余功能。
    """

    reply_ready = Signal(str, str)  # pet_id, 回复文本
    error_occurred = Signal(str, str)  # pet_id, 中文错误

    def __init__(
        self,
        pet_id: str,
        pet_name: str,
        chat_service: ChatService,
        memory: MemoryStore,
        chat_settings: ChatSettings | None = None,
        parent=None,
    ) -> None:
        """构造对话窗口。

        :param pet_id: 对话所属宠物 id。
        :param pet_name: 宠物显示名（窗口标题）。
        :param chat_service: 对话服务（持有共享 Session）。
        :param memory: 记忆存储（全量展示 + 最近 N 轮上下文）。
        :param chat_settings: 本实例合并后的对话设置（None 用全局设置）；
            已在调用方拼好实例人格与心情提示词。
        :param parent: Qt 父控件。
        """
        super().__init__(parent)
        self._pet_id = pet_id
        self._chat_service = chat_service
        self._memory = memory
        self._settings = chat_settings or chat_service._settings  # noqa: SLF001（只读兜底）
        self._busy = False

        self.setWindowTitle(f"和 {pet_name} 聊天")
        self.resize(420, 520)

        self._history_view = QTextBrowser(self)
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("说点什么…")
        self._send_btn = QPushButton("发送", self)

        bottom = QHBoxLayout()
        bottom.addWidget(self._input, 1)
        bottom.addWidget(self._send_btn)
        layout = QVBoxLayout(self)
        layout.addWidget(self._history_view, 1)
        layout.addLayout(bottom)

        self._send_btn.clicked.connect(self._on_send)
        self._input.returnPressed.connect(self._on_send)
        self.reply_ready.connect(self._on_reply)
        self.error_occurred.connect(self._on_error)

        for msg in memory.all_messages(pet_id):
            self._append_line(msg.role, msg.content)
        if not self._settings.api_key.strip():
            self._append_line("system", "还没有配置 API Key，去右键菜单 → 设置里填写吧。")

    def apply_settings(self, settings: ChatSettings) -> None:
        """更新本窗口使用的合并设置（心情/实例 API 改动后由调用方刷新）。"""
        self._settings = settings

    def _append_line(self, role: str, content: str) -> None:
        label = {"user": "你", "assistant": "宠物", "system": "系统"}.get(role, role)
        self._history_view.append(f"<b>{label}：</b>{content}")

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text or self._busy:
            return
        self._input.clear()
        self._append_line("user", text)
        self._memory.append(self._pet_id, "user", text)
        rounds = self._settings.memory_rounds
        history = self._memory.context_for(self._pet_id, rounds=rounds)[:-1]  # 最后一条是当前输入，由 send 追加
        self._busy = True
        self._send_btn.setEnabled(False)
        self._send_btn.setText("思考中…")

        def worker() -> None:
            try:
                reply = self._chat_service.send(
                    self._pet_id, text, history, settings=self._settings
                )
                self.reply_ready.emit(self._pet_id, reply)
            except ChatError as exc:
                self.error_occurred.emit(self._pet_id, exc.message)
            except Exception as exc:  # 兜底：worker 异常不能杀进程
                self.error_occurred.emit(self._pet_id, f"出错了：{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_reply(self, pet_id: str, reply: str) -> None:
        if pet_id != self._pet_id:
            return
        self._memory.append(pet_id, "assistant", reply)
        self._append_line("assistant", reply)
        self._set_idle()

    def _on_error(self, pet_id: str, message: str) -> None:
        if pet_id != self._pet_id:
            return
        self._append_line("system", f"⚠ {message}")
        self._set_idle()

    def _set_idle(self) -> None:
        self._busy = False
        self._send_btn.setEnabled(True)
        self._send_btn.setText("发送")
