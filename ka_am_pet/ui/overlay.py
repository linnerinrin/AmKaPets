"""overlay 模式窗口壳：单一大窗口承载全部宠物。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import QWidget

from ka_am_pet.ui.pet_widget import PetWidget
from ka_am_pet.world import PetWorld


class OverlayWindow(QWidget):
    """覆盖虚拟桌面的无边框、透明、置顶窗口，统一承载全部宠物。

    FramelessWindowHint | WindowStaysOnTopHint | Tool + WA_TranslucentBackground。
    空白区域鼠标穿透（保守方案：光标轮询，不在任何宠物包围盒内时整窗
    WA_TransparentForMouseEvents，悬停宠物时恢复接收输入——不整屏吞鼠标）。
    所有宠物共享同一坐标系，天然支持多宠物碰撞。
    """

    pet_clicked = Signal(str)
    menu_requested = Signal(str, QPoint)

    def __init__(
        self,
        world: PetWorld,
        pet_images: dict[str, dict[str, QPixmap]],
        geometry: tuple[int, int, int, int],
        parent: QWidget | None = None,
    ) -> None:
        """构造 overlay 窗口。

        :param world: 共享的 PetWorld。
        :param pet_images: pet_id -> (心情档位 -> QPixmap)。
        :param geometry: 虚拟桌面 (x, y, w, h)。
        :param parent: Qt 父控件。
        """
        super().__init__(parent)
        self._world = world
        gx, gy, gw, gh = geometry
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(gx, gy, gw, gh)

        origin = QPoint(gx, gy)
        self._widgets: list[PetWidget] = []
        from ka_am_pet.models import PetConfig

        for pet in world.pets:
            cfg = PetConfig(id=pet.pet_id, name=pet.pet_id, size=pet.size)
            widget = PetWidget(cfg, world, pet_images.get(pet.pet_id, {}), origin=origin, parent=self)
            widget.setWindowFlags(Qt.WindowType.Widget)  # 子控件而非顶层窗口
            widget.clicked.connect(self.pet_clicked)
            widget.menu_requested.connect(self.menu_requested)
            widget.show()
            self._widgets.append(widget)

        # 光标轮询：悬停宠物时关闭穿透，否则开启（保守方案，需手动验收记录）
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(30)
        self._hover_timer.timeout.connect(self._update_input_passthrough)
        self._hover_timer.start()

    def _update_input_passthrough(self) -> None:
        """光标在任何宠物包围盒内则接收输入，否则整窗穿透。"""
        pos = QCursor.pos()
        hit = self._world.pet_at(pos.x(), pos.y()) is not None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not hit)

    def tick(self) -> None:
        """每帧推进全部宠物控件。"""
        for widget in self._widgets:
            widget.tick()

    def music_reaction(self) -> None:
        """系统正在播放音乐时，让每只宠物做一次触摸回应动画。"""
        for widget in self._widgets:
            widget.play_music_reaction()

    def close_shell(self) -> None:
        """模式切换时关闭窗口（不退出应用）。"""
        self._hover_timer.stop()
        self.close()
