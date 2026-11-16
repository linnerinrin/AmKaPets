"""音乐律动设置数据模型（纯 dataclass，禁 Qt）。

间隔的合法范围由上层 ka_am_pet.audio.clamp_interval 决定（延迟导入，
避免 models 包与 audio 模块形成循环依赖）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..actions import clean_pool
from .coercion import coerce_bool, coerce_float
from .constants import ACTION_LABELS, MUSIC_POOL


@dataclass
class AudioSettings:
    """音乐律动设置：开关 + 动作池（可多选）+ 触发间隔（秒）。

    间隔范围见 audio.MIN/MAX_INTERVAL_SECONDS。

    ``music_pool`` 是「听歌时随机播放哪几个动作」的池子：settings 里用勾选列表
    自选，可多选；空池由播放侧回退成全表（见 actions.random_music_action）。
    老配置（v4 及更早）只有单个 ``sway_mode`` 键，读取时自动变成单元素池。
    """

    enabled: bool = True
    interval_seconds: float = 1.5
    music_pool: tuple[str, ...] = MUSIC_POOL

    @classmethod
    def from_dict(cls, raw: Any) -> "AudioSettings":
        """从配置字典解析，字段级回退默认值。"""
        # 延迟导入：ka_am_pet.audio 依赖运行时状态，models 包不反向硬依赖它。
        from ..audio import clamp_interval

        default = cls()
        if not isinstance(raw, dict):
            return default
        return cls(
            enabled=coerce_bool(raw.get("enabled"), default.enabled),
            interval_seconds=clamp_interval(coerce_float(raw.get("interval_seconds"), default.interval_seconds)),
            music_pool=_parse_pool(raw, default.music_pool),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为配置字典。"""
        return {
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "music_pool": list(self.music_pool),
        }

    def pool_label(self) -> str:
        """动作池的显示文本：单选→动作名；多选→「N 种动作随机」。"""
        labels = [ACTION_LABELS.get(key, key) for key in self.music_pool]
        if not labels:
            return "关"
        if len(labels) == 1:
            return labels[0]
        return f"{len(labels)} 种动作随机"


def _parse_pool(raw: dict[str, Any], default: tuple[str, ...]) -> tuple[str, ...]:
    """解析动作池：新键 music_pool 优先，其次兼容旧键 sway_mode（单个动作）。"""
    if "music_pool" in raw:
        pool = clean_pool(raw.get("music_pool"))
        return pool or default
    legacy = raw.get("sway_mode")
    if isinstance(legacy, str):
        pool = clean_pool(legacy)
        return pool or default
    return default


__all__ = ["AudioSettings"]
