"""desktop 模式窗口壳：每只宠物一个独立局部窗口的管理器。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from ka_am_pet.ui.pet_widget import PetWidget
from ka_am_pet.world import PetWorld


class DesktopWindow(QWidget):
    """每宠一窗壳的管理器：窗口随宠物位置移动，尺寸为宠物包围盒（正方形贴图区）。

    多窗口共享同一个 PetWorld（同一逻辑时钟与物理世界），不各自跑碰撞世界；
    非宠物区域不拦截输入（窗口本身就是宠物大小）。
    本管理器是不可见占位对象，真正的窗口是各 PetWidget。
    """

    pet_clicked = Signal(str)
    menu_requested = Signal(str, QPoint)

    def __init__(
        self,
        world: PetWorld,
        pet_images: dict[str, dict[str, QPixmap]],
        pet_names: dict[str, int],
        parent: QWidget | None = None,
    ) -> None:
        """构造 desktop 模式管理器。

        :param world: 共享的 PetWorld。
        :param pet_images: pet_id -> (心情档位 -> QPixmap)。
        :param pet_names: pet_id -> size（构造 PetWidget 用）。
        :param parent: Qt 父控件。
        """
        super().__init__(parent)
        self._world = world
        self._widgets: list[PetWidget] = []
        from ka_am_pet.models import PetConfig

        for pet in world.pets:
            cfg = PetConfig(id=pet.pet_id, name=pet.pet_id, size=pet.size)
            widget = PetWidget(cfg, world, pet_images.get(pet.pet_id, {}), parent=None)
            widget.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            widget.clicked.connect(self.pet_clicked)
            widget.menu_requested.connect(self.menu_requested)
            widget.show()
            self._widgets.append(widget)

    def tick(self) -> None:
        """每帧推进全部宠物控件。"""
        for widget in self._widgets:
            widget.tick()

    def music_reaction(self) -> None:
        """系统正在播放音乐时，让每只宠物做一次触摸回应动画。"""
        for widget in self._widgets:
            widget.play_music_reaction()

    def close_shell(self) -> None:
        """模式切换时关闭全部宠物窗口（不退出应用）。"""
        for widget in self._widgets:
            widget.close()
        self._widgets.clear()
