"""对话相关数据模型：消息、全局设置、实例覆盖与合并逻辑（纯 dataclass，禁 Qt）。

「空 = 继承全局」是 ChatOverrides 的核心语义；effective_chat 把
全局设置 + 实例覆盖 + 人格/心情提示词合成一份实际生效的设置。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coercion import coerce_int, coerce_text


@dataclass
class ChatMessage:
    """一条对话消息：role / content / ts（Unix 秒）。"""

    role: str
    content: str
    ts: float


@dataclass
class ChatSettings:
    """OpenAI 兼容 Chat Completions 的设置。"""

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    system_prompt: str = "你是桌面上的可爱桌宠，回答自然简短。"
    memory_rounds: int = 5
    timeout_seconds: int = 45

    @classmethod
    def from_dict(cls, raw: Any) -> "ChatSettings":
        """从配置字典解析，字段级回退默认值（api_key 允许空串）。"""
        default = cls()
        if not isinstance(raw, dict):
            return default
        return cls(
            base_url=coerce_text(raw.get("base_url"), default.base_url).rstrip("/"),
            api_key=coerce_text(raw.get("api_key"), "", allow_empty=True),
            model=coerce_text(raw.get("model"), default.model),
            system_prompt=coerce_text(raw.get("system_prompt"), default.system_prompt),
            memory_rounds=coerce_int(raw.get("memory_rounds"), default.memory_rounds, 1, 100),
            timeout_seconds=coerce_int(raw.get("timeout_seconds"), default.timeout_seconds, 5, 300),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为配置字典。"""
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "memory_rounds": self.memory_rounds,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class ChatOverrides:
    """单个实例的对话 API 覆盖项：空串 / 0 表示「继承全局设置」。"""

    base_url: str = ""
    api_key: str = ""
    model: str = ""
    memory_rounds: int = 0
    timeout_seconds: int = 0

    def is_empty(self) -> bool:
        """没有任何覆盖项（全部继承全局）时返回 True。"""
        return not (
            self.base_url
            or self.api_key
            or self.model
            or self.memory_rounds
            or self.timeout_seconds
        )

    @classmethod
    def from_dict(cls, raw: Any) -> "ChatOverrides":
        """从字典解析覆盖项；非法值一律视为「未覆盖」。"""
        default = cls()
        if not isinstance(raw, dict):
            return default
        return cls(
            base_url=coerce_text(raw.get("base_url"), "", allow_empty=True),
            api_key=coerce_text(raw.get("api_key"), "", allow_empty=True),
            model=coerce_text(raw.get("model"), "", allow_empty=True),
            memory_rounds=coerce_int(raw.get("memory_rounds"), default.memory_rounds, 0, 100),
            timeout_seconds=coerce_int(raw.get("timeout_seconds"), default.timeout_seconds, 0, 300),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（保持「空 = 继承」的语义）。"""
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model": self.model,
            "memory_rounds": self.memory_rounds,
            "timeout_seconds": self.timeout_seconds,
        }


def effective_chat(
    global_chat: ChatSettings,
    overrides: ChatOverrides | None = None,
    instance_prompt: str = "",
    mood_prompt: str = "",
) -> ChatSettings:
    """把全局对话设置 + 实例覆盖 + 实例人格/心情提示词合成一份新设置。

    :param global_chat: 全局 ChatSettings（缺省值的来源）。
    :param overrides: 实例级覆盖项（None 或全空 = 完全继承）。
    :param instance_prompt: 实例独立人格提示词（空则用全局 system_prompt）。
    :param mood_prompt: 心情提示词（非空则追加到系统提示词末尾）。
    :return: 合并后的新 ChatSettings（不修改入参）。
    """
    ov = overrides or ChatOverrides()
    prompt = instance_prompt.strip() or global_chat.system_prompt
    if mood_prompt.strip():
        prompt = f"{prompt}\n{mood_prompt.strip()}"
    return ChatSettings(
        base_url=(ov.base_url or global_chat.base_url).rstrip("/"),
        api_key=ov.api_key or global_chat.api_key,
        model=ov.model or global_chat.model,
        system_prompt=prompt,
        memory_rounds=ov.memory_rounds or global_chat.memory_rounds,
        timeout_seconds=ov.timeout_seconds or global_chat.timeout_seconds,
    )
