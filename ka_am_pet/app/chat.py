"""对话窗口装配：按实例打开/复用 ChatDialog，合并生效的对话设置。

ChatDialog 依赖「聊天服务协议」而非具体实现（DIP）：此处注入
ChatService；设置或心情变化后关闭旧窗口，下次打开按新设置重建。
"""

from __future__ import annotations

from dataclasses import replace

from ..theme import theme_for
from ..ui.chat_dialog import ChatDialog


class ChatMixin:
    """对话窗口的创建、复用与按实例合并对话设置。"""

    def _chat_settings_for(self, pet_id: str):
        """取实例自己的完整对话设置 + 当前心情提示词。

        第四轮起实例保存整份 ChatSettings（不再有「跟随全局」覆盖项），
        所以这里只做「人格提示词 + 心情提示词」的拼接。
        """
        assert self.settings is not None and self.world is not None
        inst = self.db.get(pet_id) if self.db is not None else None
        base = inst.overrides.chat if inst is not None else self.settings.chat
        prompt = ((inst.system_prompt if inst is not None else "") or base.system_prompt).strip()
        mood_prompt = self.world.mood_tracker(pet_id).prompt().strip()
        if mood_prompt:
            prompt = f"{prompt}\n{mood_prompt}"
        return replace(base, system_prompt=prompt)

    def _status_for(self, pet_id: str):
        """返回「状态」页的数据回调（每秒被聊天面板取一次，值未变不重绘）。"""
        def collect() -> dict[str, str]:
            assert self.world is not None and self.settings is not None
            tracker = self.world.mood_tracker(pet_id)
            mood_cfg = self.world.mood_settings_for(pet_id)
            audio = self.world.audio_for(pet_id)
            chat = self._chat_settings_for(pet_id)
            pet = self.world.get_pet(pet_id)
            pending = self.world.click_pending(pet_id)
            return {
                "名字": self._name_of(pet_id),
                "当前好感": f"{tracker.value:.0f}/100（{tracker.level}）",
                "好感下降": f"{mood_cfg.decay_per_second:g} 点/秒",
                "点击攒好感": f"{pending} / 2 次",
                "运行模式": "覆盖模式 overlay" if self.settings.mode == "overlay" else "桌面模式 desktop",
                "音乐律动": (
                    f"{'已开启' if audio.enabled else '已关闭'} · "
                    f"{audio.pool_label()} · 每 {audio.interval_seconds:g} 秒"
                ),
                "对话模型": chat.model,
                "API Key": "已配置" if chat.api_key.strip() else "未配置",
                "覆盖模式": "开（只看得见、点不到）" if (pet and pet.passthrough) else "关",
            }

        return collect

    def _open_chat(self, pet_id: str) -> None:
        """打开（或复用并刷新）某只宠物的对话窗口。"""
        assert self.world is not None and self.memory is not None and self.chat_service is not None
        dialog = self._chat_dialogs.get(pet_id)
        if dialog is None:
            dialog = ChatDialog(
                pet_id,
                self._name_of(pet_id),
                self.chat_service,
                self.memory,
                chat_settings=self._chat_settings_for(pet_id),
                status=self._status_for(pet_id),
                theme=theme_for(self.settings.theme) if self.settings is not None else None,
            )
            self._chat_dialogs[pet_id] = dialog
        else:
            dialog.apply_settings(self._chat_settings_for(pet_id))  # 心情/设置可能已变
            dialog.refresh_status()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _reset_chat_dialogs(self) -> None:
        """设置变更后关掉对话窗口，下次打开按新设置重建。"""
        for dialog in self._chat_dialogs.values():
            dialog.close()
        self._chat_dialogs.clear()
