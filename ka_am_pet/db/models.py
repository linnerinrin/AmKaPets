"""实例数据模型与 overrides_json 的序列化 / 反序列化。

纯数据层：不含任何 SQL，方便单独测试与被 schema / repository 复用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ka_am_pet.models import PetOverrides


@dataclass
class PetInstance:
    """一只桌宠实例（数据库行）。"""

    id: str
    base: str            # 基底角色 id（assets/pets/<base>/ 贴图目录）
    name: str            # 用户起的名字
    system_prompt: str = ""
    size: int = 320
    x: float | None = None
    y: float | None = None
    created_ts: float = 0.0
    overrides: PetOverrides = field(default_factory=PetOverrides)  # 实例级覆盖组
    passthrough: bool = False                                     # 覆盖模式（点不到）


def load_overrides(text: str | None) -> PetOverrides:
    """解析 overrides_json；空/损坏一律当成「用默认设置组」。

    第四轮起每实例都存完整设置，所以缺列/旧空串的行回落到
    :class:`PetOverrides` 默认值（= AppSettings 的出厂值）。
    """
    if not text:
        return PetOverrides()
    try:
        raw = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return PetOverrides()
    return PetOverrides.from_dict(raw)


def dump_overrides(overrides: PetOverrides) -> str:
    """序列化设置组；恒写完整 JSON（不再有「空组存空串」的跟随语义）。"""
    return json.dumps(overrides.to_dict(), ensure_ascii=False, sort_keys=True)
