"""鼠标交互与原生穿透 mixin：Qt 鼠标事件转交 PetWorld，WM_NCHITTEST 按区域穿透。

职责：把按下/移动/松开翻译成 PetWorld 的 start_drag / drag_to / end_drag /
pat_pet 调用（单击只播动作不加好感，好感只来自双击摸头）；
desktop 模式覆盖时身体穿透、眼睛仍可点。
物理与单击/双击判定规则见 AGENTS.md 第 5 节，本层只负责事件接入。
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from ka_am_pet.ui.pet_widget import constants as C


def _lparam_point(lparam: int) -> QPoint:
    """从 WM_NCHITTEST 的 lParam 解出屏幕坐标（支持负坐标多屏）。"""
    x = ctypes.c_short(lparam & 0xFFFF).value
    y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
    return QPoint(x, y)


class PetInteractionMixin:
    """鼠标交互与覆盖模式穿透逻辑（由 PetWidget 组合使用）。"""

    def _toggle_passthrough(self) -> None:
        """眼睛按钮点击：切换本实例的覆盖模式并持久化（由壳转交应用层）。"""
        state = self._state()
        self._world.set_passthrough(self._pet_cfg.id, not state.passthrough)
        self.update()
        self.passthrough_changed.emit(self._pet_cfg.id, state.passthrough)

    # ---- 原生命中测试：按区域穿透（desktop 模式单窗口） ----

    def nativeEvent(self, event_type, message):  # noqa: N802（Qt 命名）
        """desktop 模式下覆盖时身体区域穿透，眼睛仍可点。"""
        if event_type == b"windows_generic_MSG" and self.isWindow():
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == C.WM_NCHITTEST:
                local = QPointF(self.mapFromGlobal(_lparam_point(msg.lParam)))
                if not self._accepts_point(local):
                    return True, C.HTTRANSPARENT
                return True, C.HTCLIENT
        return super().nativeEvent(event_type, message)

    def _accepts_point(self, local: QPointF) -> bool:
        """该局部点是否应该接收鼠标（拖拽中恒接收；覆盖模式下只放行眼睛）。"""
        if self._state().dragging or self._drag_active():
            return True
        if not self.passthrough:
            return True
        return self.eye_rect().contains(local)

    def _drag_active(self) -> bool:
        return self._press_pos is not None

    # ---- 鼠标交互 ----

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self.eye_rect().contains(QPointF(event.position())):
                self._toggle_passthrough()
                event.accept()
                return
            if self.passthrough:
                event.ignore()
                return
            self._press_pos = event.globalPosition().toPoint()
            self._press_at = time.monotonic()
            self._moved = False
            self._world.start_drag(self._pet_cfg.id, self._press_pos.x(), self._press_pos.y())
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.menu_requested.emit(self._pet_cfg.id, event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._press_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            if (pos - self._press_pos).manhattanLength() > C.CLICK_MAX_MOVE_PX:
                self._moved = True
            self._world.drag_to(self._pet_cfg.id, pos.x(), pos.y())
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            self._world.end_drag(self._pet_cfg.id)
            now = time.monotonic()
            was_click = not self._moved and (now - self._press_at) * 1000 < C.CLICK_MAX_MS
            self._press_pos = None
            if was_click:
                if self._last_click_at > 0.0 and (now - self._last_click_at) * 1000 <= C.PAT_MAX_INTERVAL_MS:
                    # 双击摸头：靠两次点击的时间间隔判定；触发后重置，第三次快速点击不算
                    self._last_click_at = 0.0
                    pat_event = self._world.pat_pet(self._pet_cfg.id)
                    self.play_pat_feedback(pat_event)
                    if pat_event is not None:
                        self.pat_requested.emit(self._pet_cfg.id)
                else:
                    # 单击：只播随机动作 + 查看状态，不加好感（好感只来自双击摸头）
                    self._last_click_at = now
                    self.play_click_feedback()
                    self.clicked.emit(self._pet_cfg.id)
            event.accept()
