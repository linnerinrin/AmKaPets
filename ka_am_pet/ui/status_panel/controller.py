"""「查看状态」互动的控制器：管状态面板 + 输入条 + 气泡的显隐与跟位。

与其它互动的冲突规则：拖拽、甩抛飞行、双击摸头、发送消息、点面板外任意处，
都会退出查看状态；气泡在回复到达时出现，点击消失。
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget

from ...theme import Theme
from .widgets import ChatInputBar, SpeechBubble, StatusPanel

_PANEL_GAP = 8  # 面板/气泡与桌宠之间的纵向间距

try:  # Windows 专用：全局鼠标左键状态（桌面/别的程序的点击不会派生到本进程）
    import ctypes

    _user32 = ctypes.windll.user32
except (AttributeError, OSError):  # 非 Windows：轮询退化为永不触发，仅靠焦点/拖拽等退出
    _user32 = None


def _left_button_pressed() -> bool:
    """全局鼠标左键是否正被按下（非 Windows 恒 False）。"""
    if _user32 is None:
        return False
    try:
        return bool(_user32.GetAsyncKeyState(0x01) & 0x8000)
    except (OSError, ctypes.ArgumentError):
        return False


class StatusView(QObject):
    """「查看状态」互动的控制器：管状态面板 + 输入条 + 气泡的显隐与跟位。

    与其它互动的冲突规则：拖拽、甩抛飞行、双击摸头、发送消息、点面板外任意处，
    都会退出查看状态；气泡在回复到达时出现，点击消失。
    """

    message_sent = Signal(str, str)  # 用户在某只桌宠上发出了一条消息 (pet_id, text)

    def __init__(
        self,
        theme: Theme,
        provider: Callable[[str], dict[str, str]],
        parent: QObject | None = None,
    ) -> None:
        """构造控制器。

        :param theme: 界面主题（面板/输入条/气泡的颜色来源）。
        :param provider: (pet_id) -> 面板展示数据的回调（由应用层组装）。
        """
        super().__init__(parent)
        self._provider = provider
        self.panel = StatusPanel(theme)
        self.bar = ChatInputBar(theme)
        self.bubble = SpeechBubble(theme)
        self._pet_id: str | None = None
        self._widget: QWidget | None = None
        self._bar_bottom_offset = 0  # 输入条底边相对桌宠底边的距离（不超过桌宠底端）
        self.bar.message_sent.connect(self._forward_message)
        self.bubble.dismissed.connect(self._on_bubble_dismissed)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(500)
        self._refresh_timer.timeout.connect(self._refresh_panel)

    @property
    def pet_id(self) -> str | None:
        """当前正在查看的宠物 id（None = 不在查看状态）。"""
        return self._pet_id

    def toggle(self, pet_id: str, widget: QWidget) -> None:
        """单击桌宠：同一只再点一次退出，否则切到这只进入查看状态。"""
        if self._pet_id == pet_id:
            self.hide()
            return
        self.show(pet_id, widget)

    def show(self, pet_id: str, widget: QWidget) -> None:
        """进入查看状态：显示状态面板 + 输入条，并定时刷新。"""
        self._pet_id = pet_id
        self._widget = widget
        self.bubble.hide()
        self._refresh_panel()
        self._sync_positions()
        self.panel.show()
        self.bar.show()
        self.bar.input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._refresh_timer.start()

    def hide(self) -> None:
        """退出查看状态（气泡也一起收）。"""
        self._pet_id = None
        self._widget = None
        self.panel.hide()
        self.bar.hide()
        self.bubble.hide()
        self._refresh_timer.stop()

    def hide_panels(self) -> None:
        """只收状态面板与输入条（发送消息后：气泡等回复时再出现）。"""
        self.panel.hide()
        self.bar.hide()
        self._refresh_timer.stop()

    def set_busy(self, busy: bool) -> None:
        """请求期间的输入条状态。"""
        self.bar.set_busy(busy)

    def show_bubble(self, text: str) -> None:
        """回复到达：在桌宠上方弹气泡（与状态面板互斥，气泡说完话点一下就消失）。"""
        if self._pet_id is None or self._widget is None:
            return
        self.bubble.set_text(text)
        self._sync_positions()
        self.bubble.show()
        self.bubble.raise_()

    def sync(self, dragging: bool, flying: bool) -> None:
        """每帧同步：宠物位置跟着动；拖拽/飞行中退出查看状态。

        「点面板家族之外的任意处消失」在这里轮询判定（桌面/别的程序的点击
        不会派生到本进程，只能靠全局鼠标键状态 + 光标位置判断）。
        """
        if self._pet_id is None:
            return
        if dragging or flying:
            self.hide()
            return
        self._sync_positions()
        if _left_button_pressed() and not self._cursor_inside_family():
            self.hide()

    def _cursor_inside_family(self) -> bool:
        """光标当前是否落在面板/输入条/气泡/桌宠任一方的矩形内。"""
        pos = QCursor.pos()
        keep = (self.panel, self.bar, self.bubble, self._widget)
        return any(k is not None and k.isVisible() and k.frameGeometry().contains(pos) for k in keep)

    def _forward_message(self, text: str) -> None:
        """发送消息：立刻退出查看状态（气泡留给回复），把消息交给应用层。"""
        pet_id = self._pet_id
        self.hide_panels()
        if pet_id is not None:
            self.message_sent.emit(pet_id, text)

    def _on_bubble_dismissed(self) -> None:
        """气泡被点掉：若没有面板在显示，整个查看状态结束。"""
        if not self.panel.isVisible():
            self._pet_id = None
            self._widget = None

    def _refresh_panel(self) -> None:
        """按 provider 的最新数据刷新状态面板。"""
        if self._pet_id is None:
            return
        self.panel.refresh(self._provider(self._pet_id))

    def _sync_positions(self) -> None:
        """把面板/输入条/气泡贴到桌宠的上方与底部，并夹进所在屏幕的可用区域。

        桌宠贴屏幕右/下边缘时，居中摆放会让面板越出屏幕被裁掉（用户反馈），
        所以摆完后统一做一次屏幕边界夹取。
        """
        widget = self._widget
        if widget is None:
            return
        rect = widget.frameGeometry()
        center_x = rect.center().x()
        # 状态面板：桌宠上方居中
        self.panel.adjustSize()
        px, py = self._clamped(
            center_x - self.panel.width() // 2,
            rect.top() - self.panel.height() - _PANEL_GAP,
            self.panel.width(),
            self.panel.height(),
        )
        self.panel.move(px, py)
        # 输入条：贴桌宠底端（条底 = 桌宠底），横向居中且不超过桌宠宽度太多
        self.bar.adjustSize()
        bx, by = self._clamped(
            center_x - self.bar.width() // 2,
            rect.bottom() - self.bar.height() - self._bar_bottom_offset,
            self.bar.width(),
            self.bar.height(),
        )
        self.bar.move(bx, by)
        # 气泡：桌宠上方（在状态面板的位置一带）
        if self.bubble.isVisible():
            bx2, by2 = self._clamped(
                center_x - self.bubble.width() // 2,
                rect.top() - self.bubble.height() - _PANEL_GAP,
                self.bubble.width(),
                self.bubble.height(),
            )
            self.bubble.move(bx2, by2)

    def _clamped(self, x: int, y: int, width: int, height: int) -> tuple[int, int]:
        """把 (x, y, w, h) 的全局矩形夹进桌宠所在屏幕的可用区域（含任务栏避让）。"""
        screen = self._widget.screen() if self._widget is not None else None
        if screen is None:
            return x, max(0, y)
        area = screen.availableGeometry()
        cx = min(max(x, area.left()), max(area.left(), area.right() - width + 1))
        cy = min(max(y, area.top()), max(area.top(), area.bottom() - height + 1))
        return cx, cy

    def dispose(self) -> None:
        """关闭所有子窗口（壳层销毁/应用退出时调用）。"""
        self._refresh_timer.stop()
        for widget in (self.panel, self.bar, self.bubble):
            widget.hide()
            widget.deleteLater()
