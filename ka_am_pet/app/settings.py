"""UI 设置装配：托盘「UI 设置…」对话框的打开与保存后生效。

用户口径（第四轮）：这个对话框只剩整机外观/形态三项（运行模式、覆盖层
透明度、主题色）；物理/对话/摇摆等配置全部在实例设置里，所以这里不再
联动音频监听与实例设置组。
"""

from __future__ import annotations

from .. import config as config_mod
from ..models import AppSettings
from ..ui.settings_dialog import SettingsDialog


class SettingsMixin:
    """UI 设置对话框的打开与保存后应用。"""

    def _show_modeless(self, dialog) -> None:
        """非模态弹出对话框：持有引用防止被回收，关闭后自动释放。

        设置类窗口必须是非模态的：开着设置也要能继续和桌宠互动。
        """
        self._open_dialogs.add(dialog)
        dialog.finished.connect(lambda _code, d=dialog: self._open_dialogs.discard(d))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_settings(self) -> None:
        """打开「UI 设置」；若运行模式被改则顺手切换渲染壳。"""
        assert self.settings is not None
        old_mode = self.settings.mode
        dialog = SettingsDialog(self.settings)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.settings_saved.connect(
            lambda saved, mode=old_mode: self.switch_mode(saved.mode) if saved.mode != mode else None
        )
        self._show_modeless(dialog)

    def _on_settings_saved(self, settings: AppSettings) -> None:
        """保存：写盘并让壳透明度/主题状态面板/对话窗按新值生效。"""
        config_mod.save_config(settings, self._config_path)
        if self._shell is not None and hasattr(self._shell, "set_opacity"):
            self._shell.set_opacity(settings.overlay_opacity)
        if self._status_view is not None:
            self._status_view.dispose()  # 主题可能变了：查看状态按新主题重建
            self._status_view = self._make_status_view()
        self._rebuild_tray_menu()
        self._reset_chat_dialogs()  # 主题变了：对话窗口下次打开按新主题重建
