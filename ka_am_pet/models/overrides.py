"""实例级设置组：每个实例自带一份完整的物理 / 对话 / 律动设置（纯 dataclass，禁 Qt）。

第四轮需求（m00874）彻底删掉「跟随全局」：设置界面只在实例设置里改，
所以本类不再有 ``None = 继承`` 的语义，四组一律是完整数据。

兼容旧数据库：``from_dict`` 接收一个 ``fallback``（通常是 AppSettings 的默认值），
旧数据里「空串 / 0 = 继承」的 ChatOverrides 会被 ``effective_chat`` 合并成完整值，
缺失的 physics / music 组直接沿用 fallback。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..actions import PAT_ACTIONS, clean_pool
from .audio import AudioSettings
from .chat import ChatOverrides, ChatSettings, effective_chat
from .physics import PhysicsParams


@dataclass
class PetOverrides:
    """单实例的完整设置组：物理参数 / 对话 API / 音乐律动 / 摸头动作池。

    名字沿用历史（数据库列 overrides_json），语义已从「覆盖组」变成
    「该实例自己的设置」。
    """

    physics: PhysicsParams = field(default_factory=PhysicsParams)
    chat: ChatSettings = field(default_factory=ChatSettings)
    music: AudioSettings = field(default_factory=AudioSettings)
    pat_pool: tuple[str, ...] = PAT_ACTIONS
    """摸头（双击）随机播放的动作池；默认只有「点头摇摆」（用户口径）。"""

    def copy(self) -> "PetOverrides":
        """返回深一层的副本（对话框取默认值时用，避免共享可变对象）。"""
        return replace(
            self,
            physics=replace(self.physics),
            chat=replace(self.chat),
            music=replace(self.music),
            pat_pool=tuple(self.pat_pool),
        )

    @classmethod
    def from_dict(cls, raw: Any, fallback: "PetOverrides | None" = None) -> "PetOverrides":
        """从数据库字典解析；缺组沿用 fallback，旧版对话覆盖项自动合并成完整值。

        :param raw: overrides_json 解析后的字典（可能损坏或为旧格式）。
        :param fallback: 缺省值来源（通常是 AppSettings 的全局设置）；None 用数据类默认值。
        """
        base = fallback or cls()
        if not isinstance(raw, dict):
            return base.copy()
        physics = PhysicsParams.from_dict(raw["physics"]) if isinstance(raw.get("physics"), dict) else replace(base.physics)
        music = AudioSettings.from_dict(raw["music"]) if isinstance(raw.get("music"), dict) else replace(base.music)
        chat = _parse_chat(raw.get("chat"), base.chat)
        pool = clean_pool(raw.get("pat_pool")) or tuple(base.pat_pool)
        return cls(physics=physics, chat=chat, music=music, pat_pool=pool)

    def to_dict(self) -> dict[str, Any]:
        """序列化为完整设置字典（各组都写，永远不为空）。"""
        return {
            "physics": self.physics.to_dict(),
            "chat": self.chat.to_dict(),
            "music": self.music.to_dict(),
            "pat_pool": list(self.pat_pool),
        }


def _parse_chat(raw: Any, base: ChatSettings) -> ChatSettings:
    """解析对话设置：完整值直接用，旧版「空 = 继承」的覆盖项合并进 base。

    ``effective_chat`` 的语义正好兼容两种格式——旧数据是 base_url/model 空串
    加 0 的覆盖项（等于继承），新数据是完整值（原样返回）。
    """
    if not isinstance(raw, dict):
        return replace(base)
    return effective_chat(base, ChatOverrides.from_dict(raw))


__all__ = ["PetOverrides"]
