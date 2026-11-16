"""聊天面板：左侧分页（对话 / 状态），右侧内容区。

单击（桌面模式）或右键菜单打开；「对话」页直接聊天，「状态」页显示这只宠物的实时数值。
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ka_am_pet.models import ChatSettings
from ka_am_pet.services.memory import MemoryStore
from ka_am_pet.services.openai_chat import ChatError, ChatService
from ka_am_pet.theme import Theme

from .layout import scroll, vbox
from .sidebar import SidebarDialog


class ChatDialog(SidebarDialog):
    """宠物聊天面板：对话页 + 状态页。

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
        status: Callable[[], dict[str, str]] | None = None,
        theme: Theme | None = None,
    ) -> None:
        """构造聊天面板。

        :param pet_id: 对话所属宠物 id。
        :param pet_name: 宠物显示名（窗口标题）。
        :param chat_service: 对话服务（持有共享 Session）。
        :param memory: 记忆存储（全量展示 + 最近 N 轮上下文）。
        :param chat_settings: 本实例合并后的对话设置（None 用全局设置）；
            已在调用方拼好实例人格与心情提示词。
        :param parent: Qt 父控件。
        :param status: 可选的「实时状态」回调，返回 名称→值 的有序字典。
        :param theme: 界面主题（None 用默认淡蓝/白）。
        """
        from ka_am_pet.theme import theme_for

        super().__init__(
            f"和 {pet_name} 聊天",
            theme or theme_for(None),
            parent,
            nav_width=132,
            size=(560, 580),
            with_buttons=False,
        )
        self._pet_id = pet_id
        self._chat_service = chat_service
        self._memory = memory
        self._settings = chat_settings or chat_service._settings  # noqa: SLF001（只读兜底）
        self._status = status
        self._busy = False

        # ---- 对话页 ----
        self._history_view = QTextBrowser()
        self._input = QLineEdit()
        self._input.setPlaceholderText("说点什么…")
        self._send_btn = QPushButton("发送")
        bottom = QHBoxLayout()
        bottom.addWidget(self._input, 1)
        bottom.addWidget(self._send_btn)
        chat_page = QWidget()
        chat_layout = QVBoxLayout(chat_page)
        chat_layout.setContentsMargins(0, 0, 4, 0)
        chat_layout.setSpacing(8)
        chat_layout.addWidget(self._history_view, 1)
        chat_layout.addLayout(bottom)
        self.add_page("对话", chat_page)

        # ---- 状态页 ----
        status_widget = QWidget()
        self._status_form = QFormLayout(status_widget)
        self._status_labels: dict[str, QLabel] = {}
        self.add_page("状态", scroll(vbox(status_widget)))

        self._send_btn.clicked.connect(self._on_send)
        self._input.returnPressed.connect(self._on_send)
        self.reply_ready.connect(self._on_reply)
        self.error_occurred.connect(self._on_error)

        for msg in memory.all_messages(pet_id):
            self._append_line(msg.role, msg.content)
        if not self._settings.api_key.strip():
            self._append_line("system", "还没有配置 API Key，去右键菜单 → 设置里填写吧。")

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self.refresh_status)
        self._status_timer.start()
        self.refresh_status()

    def apply_settings(self, settings: ChatSettings) -> None:
        """更新本窗口使用的合并设置（心情/实例 API 改动后由调用方刷新）。"""
        self._settings = settings

    def refresh_status(self) -> None:
        """从回调取最新状态值刷新「状态」页（值没变就不动控件）。"""
        if self._status is None:
            return
        try:
            items = self._status()
        except Exception:  # 状态回调失败绝不能拖垮聊天
            return
        for name, value in items.items():
            label = self._status_labels.get(name)
            if label is None:
                label = QLabel()
                label.setTextInteractionFlags(label.textInteractionFlags())
                self._status_labels[name] = label
                self._status_form.addRow(name, label)
            if label.text() != value:
                label.setText(value)

    def _append_line(self, role: str, content: str) -> None:
        label = {"user": "你", "assistant": "宠物", "system": "系统"}.get(role, role)
        escaped = (
            content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        self._history_view.append(f"<b>{label}：</b>{escaped}")

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
