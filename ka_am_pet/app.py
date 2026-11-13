"""应用装配：启动器 → 实例库 → 托盘托管 → 双模式渲染壳 → 物理世界。"""

from __future__ import annotations

import logging

from PySide6.QtCore import QElapsedTimer, QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import config as config_mod
from .audio import AudioWatcher
from .db import InstanceDB, PetInstance
from .models import AppSettings, PetConfig
from .mood import MOOD_LEVELS, mood_image_name
from .resources import app_data_dir, asset_path
from .services.memory import MemoryStore
from .services.openai_chat import ChatService
from .ui.chat_dialog import ChatDialog
from .ui.desktop import DesktopWindow
from .ui.launcher import LauncherWindow
from .ui.overlay import OverlayWindow
from .ui.settings_dialog import SettingsDialog
from .world import PetWorld

_log = logging.getLogger(__name__)


class PetApplication:
    """应用主装配：配置/实例库/记忆/对话服务/渲染壳/托盘的创建与协调。"""

    def __init__(self, qt_app: QApplication) -> None:
        """保存 QApplication 引用，不创建任何窗口。

        :param qt_app: 已在 main() 中构造好的 QApplication。
        """
        self.qt_app = qt_app
        self.settings: AppSettings | None = None
        self.db: InstanceDB | None = None
        self.world: PetWorld | None = None
        self.memory: MemoryStore | None = None
        self.chat_service: ChatService | None = None
        self._shell = None  # DesktopWindow | OverlayWindow
        self._timer: QTimer | None = None
        self._elapsed = QElapsedTimer()
        self._config_path = config_mod.default_config_path()
        self._chat_dialogs: dict[str, ChatDialog] = {}
        self._tray: QSystemTrayIcon | None = None
        self._audio: AudioWatcher | None = None
        self._music_enabled = True

    # ---- 启动流程 ----

    def start(self) -> int:
        """加载配置与实例库，弹启动器选实例，构建世界/托盘并进入事件循环。

        :return: Qt 事件循环退出码，供 main() 返回。
        """
        app_data_dir().mkdir(parents=True, exist_ok=True)
        self.settings = config_mod.load_config(self._config_path)
        self.db = InstanceDB(app_data_dir() / "pets.db")
        self._ensure_default_instances()
        self.memory = MemoryStore(app_data_dir() / "memory.json", self.settings.chat.memory_rounds)
        self.chat_service = ChatService(self.settings.chat)
        self.world = PetWorld(self.settings)
        self.world.set_bounds(self._virtual_bounds())

        # 启动器：勾选本次要跑的实例
        launcher = LauncherWindow(self.db)
        launcher.instances_chosen.connect(self._spawn_instances)
        if launcher.exec() == LauncherWindow.DialogCode.Rejected or not self.world.pets:
            # 用户取消或一只都没选：直接退出（托盘也无意义）
            return 0

        self._show_shell()
        self._setup_tray()
        self._sync_audio_watcher()

        self._elapsed.start()
        self._timer = QTimer()
        self._timer.setInterval(16)  # ~60Hz
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        code = self.qt_app.exec()
        if self._audio is not None:
            self._audio.stop()
            self._audio = None
        self._save_positions()
        return code

    def _ensure_default_instances(self) -> None:
        """实例库为空时种入默认两只（超天酱 + 糖糖）。"""
        assert self.db is not None
        if not self.db.list_all():
            self.db.create("kangel", "超天酱")
            self.db.create("ame", "糖糖")

    def _spawn_instances(self, instances: list[PetInstance]) -> None:
        """把启动器勾选的实例加进世界。"""
        assert self.world is not None
        for inst in instances:
            self.world.add_pet(self._to_config(inst))

    @staticmethod
    def _to_config(inst: PetInstance) -> PetConfig:
        return PetConfig(
            id=inst.id,
            name=inst.name,
            size=inst.size,
            x=inst.x,
            y=inst.y,
            base=inst.base,
            system_prompt=inst.system_prompt,
        )

    # ---- 渲染壳 ----

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
        self._show_shell()

    def _show_shell(self) -> None:
        assert self.world is not None and self.settings is not None
        images = self._load_pet_images()
        if self.settings.mode == "overlay":
            screens = QGuiApplication.screens()
            vg = screens[0].virtualGeometry() if screens else None
            geometry = (vg.x(), vg.y(), vg.width(), vg.height()) if vg else (0, 0, 1920, 1080)
            shell = OverlayWindow(self.world, images, geometry)
            shell.show()
        else:
            shell = DesktopWindow(self.world, images, self._pet_names())
        shell.pet_clicked.connect(self._on_pet_clicked)
        shell.menu_requested.connect(self._show_menu)
        shell.tick()
        self._shell = shell

    def _tick(self) -> None:
        dt = self._elapsed.restart() / 1000.0
        if self.world is not None:
            self.world.update(dt)
        if self._shell is not None:
            self._shell.tick()
        if self._audio is not None and self._audio.take_trigger() and self._shell is not None:
            self._shell.music_reaction()

    # ---- 音乐律动（系统音频检测） ----

    def _sync_audio_watcher(self) -> None:
        """按开关启动/停止后台音频监听；设备不可用时静默跳过（不影响桌宠）。"""
        if self._music_enabled and self._audio is None:
            watcher = AudioWatcher()
            if watcher.available:
                self._audio = watcher
                watcher.start()
            else:
                _log.info("音频监听不可用，已跳过音乐律动")
        elif not self._music_enabled and self._audio is not None:
            self._audio.stop()
            self._audio = None

    def _toggle_music(self, enabled: bool) -> None:
        """右键/托盘菜单里的「音乐律动」开关。"""
        self._music_enabled = bool(enabled)
        self._sync_audio_watcher()

    def _virtual_bounds(self) -> tuple[float, float, float, float]:
        """所有屏幕可用工作区的并集 (left, top, right, bottom)。"""
        screens = QGuiApplication.screens()
        if not screens:
            return (0.0, 0.0, 1920.0, 1080.0)
        left = top = float("inf")
        right = bottom = float("-inf")
        for screen in screens:
            g = screen.availableGeometry()
            left = min(left, g.x())
            top = min(top, g.y())
            right = max(right, g.x() + g.width())
            bottom = max(bottom, g.y() + g.height())
        return (float(left), float(top), float(right), float(bottom))

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

    def _pet_names(self) -> dict[str, int]:
        assert self.world is not None
        return {p.pet_id: p.size for p in self.world.pets}

    # ---- 托盘 ----

    def _setup_tray(self) -> None:
        """创建托盘图标与右键菜单（实例列表 + 全局操作）。"""
        icon_path = asset_path("pets", "kangel", "kangel-happy.png")
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self._tray = QSystemTrayIcon(icon, self.qt_app)
        self._tray.setToolTip("ka-am-pet 桌宠")
        self._tray.activated.connect(self._on_tray_activated)
        self._rebuild_tray_menu()
        self._tray.show()

    def _rebuild_tray_menu(self) -> None:
        """重建托盘菜单：每个实例一个子菜单（对话/设置/移除），底部全局操作。"""
        assert self._tray is not None
        menu = QMenu()
        if self.world is not None:
            for pet in self.world.pets:
                sub = menu.addMenu(f"{self._name_of(pet.pet_id)}（{pet.pet_id}）")
                tracker = self.world.mood_tracker(pet.pet_id)
                mood_act = sub.addAction(f"心情 {tracker.value:.0f}/100（{tracker.level}）")
                mood_act.setEnabled(False)
                sub.addSeparator()
                sub.addAction("对话", lambda pid=pet.pet_id: self._open_chat(pid))
                sub.addAction("编辑实例", lambda pid=pet.pet_id: self._edit_instance(pid))
                sub.addAction("移除该实例", lambda pid=pet.pet_id: self._remove_instance(pid))
            menu.addSeparator()
        menu.addAction("新增实例…", self._add_instance)
        menu.addAction(
            "切换到 overlay 模式" if (self.settings and self.settings.mode == "desktop") else "切换到 desktop 模式",
            lambda: self.switch_mode("overlay" if (self.settings and self.settings.mode == "desktop") else "desktop"),
        )
        menu.addAction("全局设置…", self._open_settings)
        music_act = menu.addAction("音乐律动（听到音乐就摇摆）")
        music_act.setCheckable(True)
        music_act.setChecked(self._music_enabled)
        music_act.toggled.connect(self._toggle_music)
        menu.addSeparator()
        menu.addAction("退出", self._quit)
        self._tray.setContextMenu(menu)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._rebuild_tray_menu()  # 心情值每次左键点开时刷新

    # ---- 交互 ----

    def _name_of(self, pet_id: str) -> str:
        if self.db is not None:
            inst = self.db.get(pet_id)
            if inst is not None:
                return inst.name
        return pet_id

    def _on_pet_clicked(self, pet_id: str) -> None:
        assert self.world is not None
        self.world.click_pet(pet_id)

    def _open_chat(self, pet_id: str) -> None:
        assert self.world is not None and self.memory is not None and self.chat_service is not None
        dialog = self._chat_dialogs.get(pet_id)
        if dialog is None:
            # 独立提示词 + 心情提示词 拼接到全局 system prompt 末尾
            extras = []
            inst_prompt = ""
            if self.db is not None:
                inst = self.db.get(pet_id)
                if inst is not None:
                    inst_prompt = inst.system_prompt.strip()
            if inst_prompt:
                extras.append(inst_prompt)
            extras.append(self.world.mood_tracker(pet_id).prompt())
            dialog = ChatDialog(
                pet_id,
                self._name_of(pet_id),
                self.chat_service,
                self.memory,
                mood_prompt="\n".join(extras),
            )
            self._chat_dialogs[pet_id] = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _show_menu(self, pet_id: str, global_pos: QPoint) -> None:
        """宠物身上的右键菜单（与托盘菜单同构）。"""
        menu = QMenu()
        if self.world is not None:
            tracker = self.world.mood_tracker(pet_id)
            mood_action = menu.addAction(f"心情 {tracker.value:.0f}/100（{tracker.level}）")
            mood_action.setEnabled(False)
            menu.addSeparator()
        action_chat = menu.addAction("对话")
        action_settings = menu.addAction("全局设置")
        menu.addSeparator()
        action_mode = menu.addAction(
            "切换到 overlay 模式" if (self.settings and self.settings.mode == "desktop") else "切换到 desktop 模式"
        )
        action_music = menu.addAction("音乐律动")
        action_music.setCheckable(True)
        action_music.setChecked(self._music_enabled)
        menu.addSeparator()
        action_quit = menu.addAction("退出")
        chosen = menu.exec(global_pos)
        if chosen is action_chat:
            self._open_chat(pet_id)
        elif chosen is action_settings:
            self._open_settings()
        elif chosen is action_mode:
            self.switch_mode("overlay" if (self.settings and self.settings.mode == "desktop") else "desktop")
        elif chosen is action_music:
            self._toggle_music(action_music.isChecked())
        elif chosen is action_quit:
            self._quit()

    # ---- 实例管理（托盘菜单入口） ----

    def _add_instance(self) -> None:
        """托盘 → 新增实例：创建后立即加入世界与渲染壳。"""
        assert self.db is not None
        from .ui.launcher import InstanceEditDialog

        dlg = InstanceEditDialog()
        if dlg.exec() != InstanceEditDialog.DialogCode.Accepted:
            return
        inst = self.db.create(dlg.base, dlg.pet_name, dlg.system_prompt, dlg.size)
        self._respawn_shell()
        _log.info("新增实例 %s (%s)", inst.id, inst.name)

    def _edit_instance(self, pet_id: str) -> None:
        """托盘 → 编辑实例（名字/尺寸/提示词）；改完重建渲染壳。"""
        assert self.db is not None
        from .ui.launcher import InstanceEditDialog

        inst = self.db.get(pet_id)
        if inst is None:
            return
        dlg = InstanceEditDialog(None, inst)
        if dlg.exec() != InstanceEditDialog.DialogCode.Accepted:
            return
        inst.name = dlg.pet_name
        inst.size = dlg.size
        inst.system_prompt = dlg.system_prompt
        self.db.update(inst)
        # 尺寸可能变了：更新世界并重建壳
        if self.world is not None:
            self.world.get_pet(pet_id).size = inst.size
        self._respawn_shell()
        # 对话窗标题/提示词可能过期：关掉让它下次重建
        dialog = self._chat_dialogs.pop(pet_id, None)
        if dialog is not None:
            dialog.close()

    def _remove_instance(self, pet_id: str) -> None:
        """托盘 → 移除实例：从世界/壳/数据库中删除。"""
        assert self.db is not None and self.world is not None
        self.db.delete(pet_id)
        self.world.remove_pet(pet_id)
        dialog = self._chat_dialogs.pop(pet_id, None)
        if dialog is not None:
            dialog.close()
        self._respawn_shell()
        if not self.world.pets:
            self._quit()

    def _respawn_shell(self) -> None:
        """实例增删后重建渲染壳（世界状态保留）。"""
        if self._shell is not None:
            self._shell.close_shell()
            self._shell = None
        self._show_shell()
        self._rebuild_tray_menu()

    # ---- 设置与退出 ----

    def _open_settings(self) -> None:
        assert self.settings is not None
        old_mode = self.settings.mode
        dialog = SettingsDialog(self.settings)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()
        if self.settings.mode != old_mode:
            self.switch_mode(self.settings.mode)

    def _on_settings_saved(self, settings: AppSettings) -> None:
        config_mod.save_config(settings, self._config_path)

    def _save_positions(self) -> None:
        """退出时把每只宠物的最后位置写回实例库。"""
        if self.db is None or self.world is None:
            return
        for pet in self.world.pets:
            try:
                self.db.update_position(pet.pet_id, pet.x, pet.y)
            except Exception:  # 退出路径不抛异常
                _log.exception("保存位置失败: %s", pet.pet_id)

    def _quit(self) -> None:
        if self._audio is not None:
            self._audio.stop()
            self._audio = None
        self._save_positions()
        self.qt_app.quit()
