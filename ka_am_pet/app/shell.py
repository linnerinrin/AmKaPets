"""渲染壳装配：overlay/desktop 模式切换、贴图加载、壳重建。

渲染壳（DesktopWindow / OverlayWindow）实现同一接口可互换（LSP）：
本 mixin 只负责按当前模式创建/销毁壳并接线，不关心壳的内部实现。
"""

from __future__ import annotations

import logging

from PySide6.QtGui import QGuiApplication, QPixmap

from ..mood import MOOD_LEVELS, mood_image_name
from ..resources import asset_path
from ..ui.desktop import DesktopWindow
from ..ui.overlay import OverlayWindow

_log = logging.getLogger(__name__)


class ShellMixin:
    """模式切换与渲染壳装配（世界/记忆在切换中保留，无需重启）。"""

    def switch_mode(self, mode: str) -> None:
        """在 "overlay" 与 "desktop" 两种形态间切换（世界/记忆保留，无需重启）。"""
        if mode not in ("overlay", "desktop"):
            raise ValueError(f"不支持的模式: {mode!r}")
        if self.settings is not None and self.settings.mode == mode and self._shell is not None:
            return
        if self._shell is not None:
            self._shell.close_shell()
            self._shell = None
        if self.settings is not None:
            self.settings.mode = mode
        if self._status_view is not None:
            self._status_view.hide()
        self._show_shell()

    def _show_shell(self) -> None:
        """按当前模式创建渲染壳并接好交互信号。"""
        assert self.world is not None and self.settings is not None
        images = self._load_pet_images()
        if self.settings.mode == "overlay":
            screens = QGuiApplication.screens()
            vg = screens[0].virtualGeometry() if screens else None
            geometry = (vg.x(), vg.y(), vg.width(), vg.height()) if vg else (0, 0, 1920, 1080)
            shell = OverlayWindow(
                self.world, images, geometry, opacity=self.settings.overlay_opacity
            )
            shell.show()
        else:
            shell = DesktopWindow(self.world, images)
        shell.pet_clicked.connect(self._on_pet_clicked)
        shell.pat_requested.connect(self._on_pat_requested)
        shell.menu_requested.connect(self._show_menu)
        shell.passthrough_changed.connect(self._on_passthrough_changed)
        shell.tick(self._music_mode())
        self._shell = shell

    def _respawn_shell(self) -> None:
        """实例增删后重建渲染壳（世界状态保留）。"""
        if self._status_view is not None:
            self._status_view.hide()
        if self._shell is not None:
            self._shell.close_shell()
            self._shell = None
        self._show_shell()
        self._rebuild_tray_menu()

    def _load_pet_images(self) -> dict[str, dict[str, QPixmap]]:
        """为每只宠物按【基底角色】加载四档心情贴图；缺档回退任意可用图，全缺给 64px 透明图。"""
        assert self.world is not None
        images: dict[str, dict[str, QPixmap]] = {}
        for pet in self.world.pets:
            base = self._base_of(pet.pet_id)
            pet_imgs: dict[str, QPixmap] = {}
            for level in MOOD_LEVELS:
                path = asset_path("pets", base, mood_image_name(base, level))
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    pet_imgs[level] = pixmap
                else:
                    _log.warning("贴图缺失: %s", path)
            if not pet_imgs:
                fallback = QPixmap(64, 64)
                fallback.fill()
                for level in MOOD_LEVELS:
                    pet_imgs[level] = fallback
            else:
                any_img = next(iter(pet_imgs.values()))
                for level in MOOD_LEVELS:
                    pet_imgs.setdefault(level, any_img)
            images[pet.pet_id] = pet_imgs
        return images

    def _base_of(self, pet_id: str) -> str:
        """实例的基底角色；找不到时回退 pet_id 本身。"""
        if self.db is not None:
            inst = self.db.get(pet_id)
            if inst is not None:
                return inst.base
        return pet_id
