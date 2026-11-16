"""查看状态（StatusView）装配：面板数据、输入条对话、气泡回复。

查看状态是 desktop 模式下单击宠物弹出的状态面板 + 简易对话条；
对话请求在 worker 线程执行，回复经 _ReplyBridge 信号回到主线程弹气泡。
"""

from __future__ import annotations

import logging
import threading

from ..characters import base_label
from ..services.openai_chat import ChatError
from ..theme import theme_for
from ..ui.desktop import DesktopWindow
from ..ui.status_panel import StatusView

_log = logging.getLogger(__name__)


class StatusMixin:
    """查看状态面板的生命周期与其简易对话的消息流转。"""

    def _on_pet_clicked(self, pet_id: str) -> None:
        """单击宠物：进入/退出「查看状态」（overlay 模式桌宠只读展示，不可交互）。"""
        if self.settings is None or self.settings.mode != "desktop":
            return
        if self._status_view is None:
            return
        widget = None
        if isinstance(self._shell, DesktopWindow):
            widget = self._shell.pet_widget(pet_id)
        if widget is not None:
            self._status_view.toggle(pet_id, widget)

    def _make_status_view(self) -> StatusView:
        """按当前主题创建查看状态控制器（面板 + 输入条 + 气泡）。"""
        assert self.settings is not None
        view = StatusView(theme_for(self.settings.theme), self._status_data, self.qt_app)
        view.message_sent.connect(self._on_status_message)
        return view

    def _status_data(self, pet_id: str) -> dict[str, str]:
        """查看状态面板的展示数据（500ms 刷新一次）。"""
        assert self.world is not None
        tracker = self.world.mood_tracker(pet_id)
        audio = self.world.audio_for(pet_id)
        inst = self.db.get(pet_id) if self.db is not None else None
        base = base_label(inst.base) if inst is not None else pet_id
        return {
            "name": f"{self._name_of(pet_id)}（{base}）",
            "mood_value": str(int(round(tracker.value))),
            "mood": tracker.level,
            "music": (
                f"{audio.pool_label()} · "
                f"每 {audio.interval_seconds:g} 秒"
                if audio.enabled
                else "关"
            ),
        }

    def _on_status_message(self, pet_id: str, text: str) -> None:
        """查看状态输入条发出的消息：worker 线程请求对话，回复用气泡显示。"""
        if self.world is None or self.memory is None or self.chat_service is None:
            return
        if self._status_view is not None:
            self._status_view.set_busy(True)
        settings = self._chat_settings_for(pet_id)
        self.memory.append(pet_id, "user", text)
        context = self.memory.context_for(pet_id, rounds=settings.memory_rounds)[:-1]
        bridge = self._reply_bridge

        def work() -> None:
            try:
                reply = self.chat_service.send(settings, context, text)
            except ChatError as exc:
                bridge.replied.emit(pet_id, str(exc), False)
                return
            bridge.replied.emit(pet_id, reply, True)

        threading.Thread(target=work, daemon=True).start()

    def _on_status_reply(self, pet_id: str, text: str, ok: bool) -> None:
        """worker 回复回主线程：成功则写入记忆并弹气泡。"""
        if ok and self.memory is not None:
            self.memory.append(pet_id, "assistant", text)
        if self._status_view is not None:
            self._status_view.set_busy(False)
            if self._status_view.pet_id == pet_id:
                self._status_view.show_bubble(text if ok else f"出错了：{text}")
