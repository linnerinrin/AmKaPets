"""托盘与右键菜单：托盘图标、实例列表、宠物右键菜单。

用户口径（第四轮）：
- 宠物右键只保留「对话 / 实例设置… / 覆盖模式 / 退出」；
- 托盘右键只保留「实例列表 / 新增实例… / 让她们摇摆一下 / UI 设置… / 退出」；
- 原来的「窗口模式」「全局设置」「音乐律动」全部删除（窗口形态走左上角眼睛，
  律动改成每个实例在设置里勾选，全局设置瘦身成「UI 设置」）。
每次打开前重建，保证覆盖勾选等状态是最新的。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import __version__
from ..resources import asset_path


class TrayMixin:
    """系统托盘图标与托盘/宠物右键菜单的构建。"""

    def _setup_tray(self) -> None:
        """创建托盘图标与右键菜单（实例列表 + 新增 + 摇摆预览 + UI 设置 + 退出）。"""
        icon_path = asset_path("pets", "kangel", "kangel-happy.png")
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self._tray = QSystemTrayIcon(icon, self.qt_app)
        self._tray.setToolTip(f"ka-am-pet 桌宠 v{__version__}")
        self._tray.activated.connect(self._on_tray_activated)
        self._rebuild_tray_menu()
        self._tray.show()

    def _add_pet_actions(self, menu: QMenu, pet_id: str, *, include_remove: bool = False) -> None:
        """把「对话 / 实例设置… / 覆盖模式」加到菜单上（托盘与宠物右键共用）。

        为什么抽出来：托盘实例子菜单与宠物右键曾各写一遍同样的三项，改一处就漏另一处；
        唯一差异（托盘多一项「移除该实例」）用参数表达，动作实现只保留一份。
        """
        pet = self.world.get_pet(pet_id) if self.world is not None else None
        menu.addAction("对话", lambda pid=pet_id: self._open_chat(pid))
        menu.addAction("实例设置…", lambda pid=pet_id: self._edit_instance(pid))
        cover_act = menu.addAction("覆盖模式")
        cover_act.setCheckable(True)
        cover_act.setChecked(bool(pet and pet.passthrough))
        cover_act.toggled.connect(
            lambda checked, pid=pet_id: self._set_passthrough(pid, checked)
        )
        if include_remove:
            menu.addAction("移除该实例", lambda pid=pet_id: self._remove_instance(pid))

    def _rebuild_tray_menu(self) -> None:
        """重建托盘菜单：实例列表（子菜单）+ 新增实例 + 摇摆预览 + UI 设置 + 退出。"""
        assert self._tray is not None
        menu = QMenu()
        instances = menu.addMenu("实例列表")
        if self.world is not None:
            for pet in self.world.pets:
                sub = instances.addMenu(f"{self._name_of(pet.pet_id)}（{pet.pet_id}）")
                self._add_pet_actions(sub, pet.pet_id, include_remove=True)
        if instances.isEmpty():
            empty = instances.addAction("（还没有实例）")
            empty.setEnabled(False)
        menu.addAction("新增实例…", self._add_instance)
        menu.addAction("让她们摇摆一下", self._preview_music_reaction)
        menu.addAction("UI 设置…", self._open_settings)
        menu.addSeparator()
        menu.addAction("退出", self._quit)
        self._tray.setContextMenu(menu)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._rebuild_tray_menu()  # 每次左键点开时刷新

    def _show_menu(self, pet_id: str, global_pos: QPoint) -> None:
        """宠物身上的右键菜单：对话 / 实例设置… / 覆盖模式 / 退出。"""
        menu = QMenu()
        self._add_pet_actions(menu, pet_id)
        menu.addSeparator()
        menu.addAction("退出", self._quit)
        menu.exec(global_pos)
