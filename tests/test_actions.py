"""动作表（抽象动作接口）的纯逻辑测试。"""

from __future__ import annotations

import random

from ka_am_pet import actions


def test_action_lookup_and_fallback():
    assert actions.action("nod").kind == "stretch"
    assert actions.action("sway").kind == "flip"
    assert actions.action("pat").label == "摸头"
    # 未知键回退点头，不能抛异常
    assert actions.action("nonsense").key == "nod"
    assert actions.action_label("nonsense") == actions.action_label("nod")


def test_sway_flips_are_even():
    """左右摇摆必须转偶数次，才不会停在镜像那一侧。"""
    assert actions.action("sway").flips % 2 == 0
    assert actions.action("nod").flips == 1


def test_random_click_action_stays_in_click_set():
    rng = random.Random(7)
    picks = {actions.random_click_action(rng).key for _ in range(80)}
    assert picks <= set(actions.CLICK_ACTIONS)
    assert len(picks) == 2  # 点头与左右摇摆都会被抽到


def test_click_cooldown_is_longest_action():
    assert actions.CLICK_COOLDOWN_SECONDS == max(a.duration for a in actions.ACTIONS.values())
    assert actions.CLICK_COOLDOWN_SECONDS == actions.MAX_ACTION_SECONDS


def test_pat_is_fixed_to_first_action():
    """摸头固定播动作 1（点头摇摆），不再随机（第三轮用户口径）。"""
    assert actions.PAT_ACTIONS == (actions.ACTION_TABLE[1],)
    assert actions.pat_action().key == "nod"


def test_action_table_is_one_based_and_complete():
    """动作编号表：从 1 起、按登记顺序、与 ACTIONS 一一对应（用户口径 dict[idx]）。"""
    assert actions.ACTION_TABLE[1] == "nod"
    assert actions.ACTION_TABLE[len(actions.ACTIONS)] == "pat"
    assert set(actions.ACTION_TABLE.values()) == set(actions.ACTIONS)
    assert actions.action_by_index(1).key == "nod"
    assert actions.action_by_index(3).key == "pat"
    # 越界/非法编号回退点头摇摆，不能抛异常
    assert actions.action_by_index(0).key == "nod"
    assert actions.action_by_index(99).key == "nod"


def test_music_pool_covers_every_action():
    """听歌可选用动作 = 动作表全集（用户口径：设置里能勾所有动画）。"""
    assert set(actions.MUSIC_ACTIONS) == set(actions.ACTIONS)


def test_random_pool_action_respects_pool():
    """勾了几个就只在几个里随机：单元素池等价于固定动作。"""
    rng = random.Random(5)
    assert {actions.random_pool_action(("sway",), rng=rng).key for _ in range(20)} == {"sway"}
    picks = {actions.random_pool_action(("nod", "pat"), rng=rng).key for _ in range(120)}
    assert picks == {"nod", "pat"}  # 池外动作不会被抽到


def test_random_pool_action_falls_back():
    """池子为空或全是非法 key 时回退 fallback，不能变成不动或抛异常。"""
    rng = random.Random(9)
    for pool in ((), None, ("nonsense",)):
        picks = {actions.random_pool_action(pool, rng=rng).key for _ in range(120)}
        assert picks == set(actions.MUSIC_ACTIONS)
    # 自定义 fallback：摸头默认池只有「点头摇摆」
    assert actions.random_pool_action((), actions.PAT_ACTIONS, rng).key == "nod"


def test_clean_pool_orders_and_filters():
    """池子规整：按动作表顺序输出、去重、丢弃未知项。"""
    assert actions.clean_pool(["pat", "nod", "pat", "nope"]) == ("nod", "pat")
    assert actions.clean_pool("sway") == ("sway",)  # 兼容旧配置的单动作字符串
    assert actions.clean_pool(None) == ()
