"""应用装配核心：启动流程、主循环 tick、屏幕边界与退出。

本模块只负责 PetApplication 的「骨架」职责：
构造状态字段、加载配置/实例库、弹启动器、启动 60Hz 定时器、优雅退出。
渲染壳、托盘、对话、实例管理等职责拆在同包的 mixin 模块中。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from .. import config as config_mod
from ..db import InstanceDB, PetInstance
from ..models import AppSettings, PetConfig
from ..resources import app_data_dir, data_dir_note
from ..services.memory import MemoryStore
from ..services.openai_chat import ChatService
from ..ui.launcher import LauncherWindow
from ..ui.status_panel import StatusView
from ..world import PetWorld

_log = logging.getLogger(__name__)


class _ReplyBridge(QObject):
    """查看状态聊天气泡：worker 线程的回复通过信号回到主线程。"""

    replied = Signal(str, str, bool)  # pet_id, 回复或错误文本, 是否成功


class AppCore:
    """应用核心状态与启动/退出流程；具体功能由 mixin 补足。"""

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
        self._chat_dialogs = {}
        self._tray = None
        self._audio = None
        self._status_view: StatusView | None = None
        self._reply_bridge = _ReplyBridge()
        self._reply_bridge.replied.connect(self._on_status_reply)
        self._open_dialogs = set()  # 非模态设置/实例对话框（防回收）

    # ---- 启动流程 ----

    def start(self) -> int:
        """加载配置与实例库，弹启动器选实例，构建世界/托盘并进入事件循环。

        :return: Qt 事件循环退出码，供 main() 返回。
        """
        data_dir = app_data_dir()
        self.settings = config_mod.load_config(self._config_path)
        self.db = InstanceDB(data_dir / "pets.db")
        self._ensure_default_instances()
        self.memory = MemoryStore(data_dir / "memory.json", self.settings.chat.memory_rounds)
        self._warn_data_dir(data_dir)
        self.chat_service = ChatService(self.settings.chat)
        self.world = PetWorld(self.settings)
        self.world.set_bounds(self._virtual_bounds())

        # 启动器：勾选本次要跑的实例
        launcher = LauncherWindow(self.db, self.settings)
        launcher.instances_chosen.connect(self._spawn_instances)
        if launcher.exec() == LauncherWindow.DialogCode.Rejected or not self.world.pets:
            # 用户取消或一只都没选：直接退出（托盘也无意义）
            return 0

        self._show_shell()
        self._setup_tray()
        self._sync_audio_watcher()
        self._status_view = self._make_status_view()

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

    def _warn_data_dir(self, data_dir: Path) -> None:
        """数据目录降级或实例库改用应急副本时给一次中文提示。

        同样的提示内容只弹一次（记录在数据目录里），避免每次启动都挡一次弹窗；
        内容变化（换目录、换原因）会重新提示。
        """
        notes = [data_dir_note()]
        if self.db is not None and self.db.recovered_note:
            notes.append(self.db.recovered_note)
        messages = [note for note in notes if note]
        if not messages:
            return
        text = "\n\n".join(messages) + f"\n\n本次数据目录：{data_dir}"
        _log.warning("数据目录提示：%s", text)
        marker = data_dir / ".notice-shown"
        try:
            if marker.read_text(encoding="utf-8") == text:
                return
        except OSError:
            pass
        QMessageBox.warning(None, "数据目录提示", text)
        try:
            marker.write_text(text, encoding="utf-8")
        except OSError:
            pass  # 提示记不下来也无所谓，最多下次再弹一次

    def _ensure_default_instances(self) -> None:
        """实例库为空时种入默认两只（超天酱 + 糖糖）。"""
        assert self.db is not None
        if not self.db.list_all():
            self.db.create("kangel", "超天酱")
            self.db.create("ame", "糖糖")

    def _spawn_instances(self, instances: list[PetInstance]) -> None:
        """把启动器勾选的实例加进世界（带实例级覆盖组与覆盖模式）。"""
        assert self.world is not None
        for inst in instances:
            self.world.add_pet(
                self._to_config(inst), overrides=inst.overrides, passthrough=inst.passthrough
            )

    @staticmethod
    def _to_config(inst: PetInstance) -> PetConfig:
        """数据库实例 → 世界用的 PetConfig（不含覆盖组，覆盖单独传）。"""
        return PetConfig(
            id=inst.id,
            name=inst.name,
            size=inst.size,
            x=inst.x,
            y=inst.y,
            base=inst.base,
            system_prompt=inst.system_prompt,
        )

    # ---- 主循环 ----

    def _tick(self) -> None:
        """~60Hz：用真实时间差推进物理世界，并同步渲染壳与查看状态面板。"""
        dt = self._elapsed.restart() / 1000.0
        if self.world is not None:
            self.world.update(dt)
        if self._shell is not None:
            self._shell.tick(self._music_mode())
        if self._status_view is not None and self._status_view.pet_id is not None:
            pet = self.world.get_pet(self._status_view.pet_id) if self.world is not None else None
            self._status_view.sync(bool(pet and pet.dragging), bool(pet and pet.flying))

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

    # ---- 退出 ----

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
        """停音频监听、销毁查看状态、保存位置后退出 Qt 事件循环。"""
        if self._audio is not None:
            self._audio.stop()
            self._audio = None
        if self._status_view is not None:
            self._status_view.dispose()
            self._status_view = None
        self._save_positions()
        self.qt_app.quit()
