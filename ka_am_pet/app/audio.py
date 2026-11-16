"""音乐律动装配：系统音频监听器的按需启停。

AudioWatcher 在后台线程监听系统音频；只有任一宠物启用律动时才启动，
全部关闭或退出时立即停止，避免无意义占用设备。

用户口径（第四轮）：托盘/宠物右键里的「音乐律动」开关已删除——是否律动
改成每个实例在「实例设置 → 交互 → 摇摆」里单独勾选，所以这里不再有
「改全局开关」的入口，只剩监听器的启动/停止与菜单预览。
"""

from __future__ import annotations

import logging

from ..audio import AudioWatcher

_log = logging.getLogger(__name__)


class AudioMixin:
    """音乐律动（系统音频检测）相关的开关与生命周期管理。"""

    def _music_mode(self) -> bool:
        """是否已进入音乐模式（连续听到音乐 20~60 秒后才算，概率线性增长）。"""
        return self._audio is not None and self._audio.music_mode

    def _music_wanted(self) -> bool:
        """是否有任一宠物启用音乐律动（全局或实例覆盖）。"""
        if self.world is None:
            return False
        return any(self.world.audio_for(pet.pet_id).enabled for pet in self.world.pets)

    def _sync_audio_watcher(self) -> None:
        """按「是否有人要听音乐」启动/停止后台音频监听；设备不可用时静默跳过。"""
        wanted = self._music_wanted()
        if wanted and self._audio is None:
            watcher = AudioWatcher()
            if watcher.available:
                self._audio = watcher
                watcher.start()
            else:
                _log.info("音频监听不可用，已跳过音乐律动")
        elif not wanted and self._audio is not None:
            self._audio.stop()
            self._audio = None

    def _preview_music_reaction(self) -> None:
        """托盘菜单「让她们摇摆一下」：立即播一次摇摆反应。"""
        if self._shell is not None:
            self._shell.music_reaction()
