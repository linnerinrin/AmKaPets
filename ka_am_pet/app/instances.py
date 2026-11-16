"""实例生命周期管理：新增/编辑/移除实例，覆盖模式与摸头联动。

实例数据落在 InstanceDB，运行时状态在 PetWorld；本 mixin 负责
两侧的一致性（改完立刻同步世界并重建渲染壳/托盘菜单）。
"""

from __future__ import annotations

import logging

from ..ui.settings_dialog import InstanceSettingsDialog

_log = logging.getLogger(__name__)


class InstancesMixin:
    """托盘入口的实例增删改，以及覆盖模式/摸头的状态同步。"""

    def _name_of(self, pet_id: str) -> str:
        """实例显示名；找不到时回退 pet_id。"""
        if self.db is not None:
            inst = self.db.get(pet_id)
            if inst is not None:
                return inst.name
        return pet_id

    def _on_pat_requested(self, pet_id: str) -> None:
        """双击摸头：好感值变了，刷新托盘菜单上的心情显示。"""
        _log.debug("摸头: %s", pet_id)
        self._rebuild_tray_menu()

    def _on_passthrough_changed(self, pet_id: str, passthrough: bool) -> None:
        """眼睛按钮切换覆盖模式：写回实例库（世界状态已由控件更新）。"""
        if self.db is not None:
            self.db.set_passthrough(pet_id, passthrough)
        self._rebuild_tray_menu()
        _log.info("实例 %s 覆盖模式 = %s", pet_id, passthrough)

    def _set_passthrough(self, pet_id: str, passthrough: bool) -> None:
        """菜单里切换覆盖模式（控件会在下一帧同步窗口属性与眼睛外观）。"""
        if self.world is not None:
            self.world.set_passthrough(pet_id, passthrough)
        if self.db is not None:
            self.db.set_passthrough(pet_id, passthrough)

    def _add_instance(self) -> None:
        """托盘 → 新增实例：非模态打开（设置开着也能继续玩桌宠），保存后立即加入世界。"""
        assert self.db is not None and self.world is not None and self.settings is not None
        dlg = InstanceSettingsDialog(self.settings)
        dlg.accepted.connect(lambda: self._on_instance_created(dlg))
        self._show_modeless(dlg)

    def _on_instance_created(self, dlg: InstanceSettingsDialog) -> None:
        """新增实例对话框保存后的落库与世界装配。"""
        assert self.db is not None and self.world is not None
        result = dlg.result_instance
        inst = self.db.create(
            result.base,
            result.name,
            result.system_prompt,
            result.size,
            overrides=result.overrides,
            passthrough=result.passthrough,
        )
        self.world.add_pet(
            self._to_config(inst), overrides=inst.overrides, passthrough=inst.passthrough
        )
        self._respawn_shell()
        _log.info("新增实例 %s (%s)", inst.id, inst.name)

    def _edit_instance(self, pet_id: str) -> None:
        """托盘 → 编辑实例：非模态打开；保存后改名/尺寸/设置组并重建渲染壳。"""
        assert self.db is not None and self.settings is not None
        inst = self.db.get(pet_id)
        if inst is None:
            return
        dlg = InstanceSettingsDialog(
            self.settings,
            inst,
            mood_view=self._mood_view(pet_id),
            history=self.memory.all_messages(pet_id) if self.memory is not None else (),
        )
        dlg.practice_toggled.connect(lambda on, pid=pet_id: self._set_practice(pid, on))
        dlg.accepted.connect(lambda: self._on_instance_saved(pet_id, dlg))
        self._show_modeless(dlg)

    def _mood_view(self, pet_id: str) -> dict[str, dict[str, object]]:
        """实例设置里「当前状态」卡片的数据（好感值 / 档位 / 直播练习）。"""
        if self.world is None:
            return {}
        tracker = self.world.mood_tracker(pet_id)
        return {
            "mood": {
                "value": tracker.value,
                "level": tracker.level,
                "practice": self.world.practice_on(pet_id),
            }
        }

    def _set_practice(self, pet_id: str, on: bool) -> None:
        """直播练习开关：心情钉在 100 且不下降；关闭时恢复进入前的值。"""
        if self.world is None:
            return
        self.world.set_practice(pet_id, on)
        _log.info("实例 %s 直播练习 = %s", pet_id, on)

    def _on_instance_saved(self, pet_id: str, dlg: InstanceSettingsDialog) -> None:
        """编辑实例对话框保存后的应用。"""
        assert self.db is not None
        updated = dlg.result_instance
        self.db.update(updated)
        if self.world is not None:
            self.world.set_overrides(pet_id, updated.overrides)
            self.world.set_passthrough(pet_id, updated.passthrough)
            self.world.get_pet(pet_id).size = updated.size
        self._sync_audio_watcher()
        self._respawn_shell()
        # 对话窗的提示词/API 可能过期：关掉让它下次重建
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
        self._sync_audio_watcher()
        self._respawn_shell()
        if not self.world.pets:
            self._quit()
