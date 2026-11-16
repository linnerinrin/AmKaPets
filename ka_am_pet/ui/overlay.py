"""overlay 模式窗口壳：单一大窗口承载全部宠物。

与 desktop 的差异只有「窗口承载方式」：这里是一个覆盖虚拟桌面的透明置顶窗口，
宠物控件是它的子控件并带屏幕原点偏移；装配/tick/信号转发继承自 :class:`PetShell`。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from ka_am_pet.models import PetState
from ka_am_pet.ui.pet_widget import PetWidget
from ka_am_pet.ui.shell_base import PetShell
from ka_am_pet.world import PetWorld

__all__ = ["OverlayWindow"]

_WM_NCHITTEST = 0x0084
_HTTRANSPARENT = -1
_HTCLIENT = 1


def _lparam_point(lparam: int) -> QPoint:
    """从 WM_NCHITTEST 的 lParam 解出屏幕坐标（支持负坐标多屏）。"""
    x = ctypes.c_short(lparam & 0xFFFF).value
    y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
    return QPoint(x, y)


class OverlayWindow(PetShell):
    """覆盖虚拟桌面的无边框、透明、置顶窗口，统一承载全部宠物。

    空白区域鼠标穿透改用 **WM_NCHITTEST 按区域判定**（HTTRANSPARENT），
    比光标轮询可靠：光标在宠物身体上才接收点击，在空白处/覆盖模式的宠物身上
    直接落到下面的应用，而左上角眼睛按钮任何时候都点得到。
    """

    def __init__(
        self,
        world: PetWorld,
        pet_images: dict[str, dict[str, QPixmap]],
        geometry: tuple[int, int, int, int],
        opacity: float = 0.92,
        parent: QWidget | None = None,
    ) -> None:
        """构造 overlay 窗口。

        :param world: 共享的 PetWorld。
        :param pet_images: pet_id -> (心情档位 -> QPixmap)。
        :param geometry: 虚拟桌面 (x, y, w, h)。
        :param opacity: 整层不透明度（0.2~1.0），用于让桌宠更「贴」在桌面上。
        :param parent: Qt 父控件。
        """
        # 子类钩子（_prepare/_create_widget）在 super().__init__ 里被调用，
        # 所以窗口几何/原点必须在调用父类构造之前就准备好。
        self._geometry = geometry
        self._origin = QPoint(geometry[0], geometry[1])
        self._opacity = opacity
        super().__init__(world, pet_images, parent)

    def _prepare(self) -> None:
        """设置无边框/置顶/透明与整层几何、不透明度。"""
        gx, gy, gw, gh = self._geometry
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(gx, gy, gw, gh)
        self.set_opacity(self._opacity)

    def _create_widget(self, pet: PetState, images: dict[str, QPixmap]) -> PetWidget:
        """造一个本窗口的子控件（带屏幕原点偏移）。"""
        widget = self._make_widget(pet, images, parent=self, origin=self._origin)
        widget.setWindowFlags(Qt.WindowType.Widget)  # 子控件而非顶层窗口
        return widget

    def set_opacity(self, opacity: float) -> None:
        """设置整层不透明度（0.2~1.0，越低越「虚化」）。"""
        self.setWindowOpacity(max(0.2, min(1.0, float(opacity))))

    # ---- 按区域穿透 ----

    def nativeEvent(self, event_type, message):  # noqa: N802（Qt 命名）
        """命中测试：只有宠物身体 / 眼睛按钮受理鼠标，其余区域穿透到桌面。"""
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == _WM_NCHITTEST:
                local = self.mapFromGlobal(_lparam_point(msg.lParam))
                return True, (_HTCLIENT if self._accepts(local) else _HTTRANSPARENT)
        return super().nativeEvent(event_type, message)

    def _accepts(self, local: QPoint) -> bool:
        """该点是否该由 overlay 接收。

        用户口径：overlay 模式下桌宠只读展示（不可点击/拖拽/查看状态），
        唯一例外是左上角眼睛按钮（切换覆盖模式），所以只放行眼睛区域。
        """
        for widget in self.widgets:
            rect = widget.geometry()
            if not rect.contains(local):
                continue
            eye = widget.eye_rect().translated(rect.topLeft())
            if eye.contains(local):
                return True
        return False

    def close_shell(self) -> None:
        """模式切换时关闭宠物控件与本窗口（不退出应用）。"""
        super().close_shell()
        self.close()
