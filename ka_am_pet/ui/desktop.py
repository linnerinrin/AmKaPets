"""desktop 模式窗口壳：每只宠物一个独立局部窗口的管理器。

本类只剩「每宠一窗」的差异：控件不带父窗口、坐标原点就是屏幕原点；
控件装配、信号转发、每帧推进与关闭逻辑全部继承自 :class:`PetShell`。
"""

from __future__ import annotations

from PySide6.QtGui import QPixmap

from ka_am_pet.models import PetState
from ka_am_pet.ui.pet_widget import PetWidget
from ka_am_pet.ui.shell_base import PetShell

__all__ = ["DesktopWindow"]


class DesktopWindow(PetShell):
    """每宠一窗壳的管理器：窗口随宠物位置移动，尺寸为宠物包围盒（正方形贴图区）。

    多窗口共享同一个 PetWorld（同一逻辑时钟与物理世界），不各自跑碰撞世界；
    覆盖模式下宠物窗口用 WM_NCHITTEST 把身体区域让给桌面，眼睛按钮仍可点。
    本管理器是不可见占位对象，真正的窗口是各 PetWidget。
    """

    def _create_widget(self, pet: PetState, images: dict[str, QPixmap]) -> PetWidget:
        """造一个顶层宠物窗口（无父控件、原点即屏幕原点）。"""
        return self._make_widget(pet, images)
