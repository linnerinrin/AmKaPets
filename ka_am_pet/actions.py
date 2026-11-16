"""宠物动作抽象层（纯 Python，禁 Qt）。

设计目标（一个接口对应多个动画）：
- 每个动作只登记一份 :class:`ActionSpec`：key、显示名、渲染方式、时长、翻转次数；
- UI（:mod:`ka_am_pet.ui.pet_widget`）只消费规格，不关心这个动作是点击、摸头还是
  音乐律动触发的；
- 想加新动作（比如「转圈」「挥手」）：在这里登记一条，再在 PetWidget 的渲染里补一个
  渲染方式分支即可被所有入口复用，不用改点击/音乐/设置逻辑。
- 动作带编号（:data:`ACTION_TABLE`，从 1 起）：用户口径「数字对应动画名，
  dict[idx] 取动作」，摸头、音乐律动等入口都用编号说话，不硬编码 key。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ActionSpec:
    """一个可播放动作的完整规格。"""

    key: str                 # 动作标识（也是设置里动作池的取值）
    label: str               # 中文显示名（设置/提示用）
    kind: str                # 渲染方式："stretch"（拉伸）/ "squish"（压扁回弹）/ "flip"（镜像反转）
    duration: float          # 动画总时长（秒），点击冷却也取这里的最大值
    flips: int = 1           # kind="flip" 时翻转次数；偶数次 = 回到原来的朝向


#: 全部动作。新增动作只需在这里加一条。
ACTIONS: dict[str, ActionSpec] = {
    "nod": ActionSpec(key="nod", label="点头摇摆", kind="stretch", duration=0.26),
    "sway": ActionSpec(key="sway", label="左右摇摆", kind="flip", duration=0.40, flips=2),
    # 摸头用独立渲染方式 "squish"：与点头的 stretch 视觉区分（纵压回弹、锚定脚底）
    "pat": ActionSpec(key="pat", label="摸头", kind="squish", duration=0.34),
}

#: 动作编号表（从 1 起）：用户口径「数字对应动画名，dict[idx] 取动作」。
ACTION_TABLE: dict[int, str] = {index: key for index, key in enumerate(ACTIONS, start=1)}

#: 动作 1：点头摇摆（摸头固定播它、单击随机池也包含它）。
FIRST_ACTION_KEY: str = ACTION_TABLE[1]

#: 单击时随机播放的动作（未来加「转圈」等，往这里追加即可）。
CLICK_ACTIONS: tuple[str, ...] = ("nod", "sway")

#: 摸头（双击）默认动作池 = 动作表第 1 号（用户口径：默认只勾「点头摇摆」）。
PAT_ACTIONS: tuple[str, ...] = (FIRST_ACTION_KEY,)

#: 音乐律动可选动作 = 动作表全集；真正播哪几个由设置里的动作池（可多选）决定。
MUSIC_ACTIONS: tuple[str, ...] = tuple(ACTION_TABLE.values())

#: 全部动作里最长的时长：点击好感冷却按它算，保证动画播完才算下一次点击。
MAX_ACTION_SECONDS: float = max(spec.duration for spec in ACTIONS.values())

#: 点击好感冷却（秒）。
CLICK_COOLDOWN_SECONDS: float = MAX_ACTION_SECONDS


def action(key: str) -> ActionSpec:
    """按 key 取动作规格；未知 key 回退动作 1，保证永不抛异常。"""
    return ACTIONS.get(key) or ACTIONS[FIRST_ACTION_KEY]


def action_label(key: str) -> str:
    """动作显示名（用于菜单/提示）。"""
    return action(key).label


def action_by_index(index: int) -> ActionSpec:
    """按动作编号（从 1 起）取规格；越界或非法编号回退动作 1。"""
    key = ACTION_TABLE.get(int(index))
    return action(key) if key else ACTIONS[FIRST_ACTION_KEY]


def pat_action() -> ActionSpec:
    """摸头默认动作（动作表第 1 号）：动作池为空时的兜底展示。"""
    return action_by_index(1)


def random_click_action(rng=None) -> ActionSpec:
    """随机挑一个单击动作（默认不连续重复由调用方自行控制）。"""
    picker = rng or random
    return action(picker.choice(CLICK_ACTIONS))


def clean_pool(pool: object) -> tuple[str, ...]:
    """把设置里的动作池规整成合法 key 元组（按动作表顺序、去重、丢弃未知项）。

    :param pool: 任意输入（配置里可能是 list / tuple / 单个字符串 / None）。
    :return: 合法 key 元组；空结果由调用方决定回退策略（播放时回退全表）。
    """
    if isinstance(pool, str):
        pool = (pool,)
    if not isinstance(pool, (list, tuple, set)):
        return ()
    wanted = {item for item in pool if isinstance(item, str)}
    return tuple(key for key in ACTIONS if key in wanted)


def random_pool_action(
    pool: Sequence[str] | None,
    fallback: Sequence[str] = MUSIC_ACTIONS,
    rng=None,
) -> ActionSpec:
    """从动作池里随机挑一个动作（摸头与音乐律动共用）。

    :param pool: 勾选的动作 key 序列；为空或全非法时回退到 fallback。
    :param fallback: 池子为空时的兜底动作序列（摸头传 PAT_ACTIONS，摇摆传全表）。
    """
    keys = clean_pool(pool) or tuple(fallback)
    picker = rng or random
    return action(picker.choice(keys))


__all__ = [
    "ACTIONS",
    "ACTION_TABLE",
    "CLICK_ACTIONS",
    "CLICK_COOLDOWN_SECONDS",
    "FIRST_ACTION_KEY",
    "MAX_ACTION_SECONDS",
    "MUSIC_ACTIONS",
    "PAT_ACTIONS",
    "ActionSpec",
    "action",
    "action_by_index",
    "action_label",
    "clean_pool",
    "pat_action",
    "random_click_action",
    "random_pool_action",
]
