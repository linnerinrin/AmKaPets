"""多宠物碰撞测试（纯函数，不碰 Qt）。"""

import math

from ka_am_pet import collision
from ka_am_pet.models import PetState


def _pet(pid, x, y, vx=0.0, vy=0.0, size=320, flying=False):
    return PetState(pet_id=pid, x=x, y=y, vx=vx, vy=vy, size=size, flying=flying)


def test_equal_mass_head_on_swaps_normal_velocity():
    """等质量正碰近似交换法向速度，切向速度不变。"""
    # 两只等高宠物水平重叠；p1 以 800px/s 向右撞静止的 p2
    p1 = _pet("a", 0.0, 0.0, vx=800.0, vy=100.0, flying=True)
    p2 = _pet("b", 300.0, 0.0, vx=0.0, vy=50.0, flying=False)
    assert collision.resolve_pair_collision(p1, p2)
    # 法向为水平方向；e=0.995 等质量：近似交换法向速度
    assert math.isclose(p1.vx, 0.0, abs_tol=5.0)
    assert math.isclose(p2.vx, 800.0, abs_tol=5.0)
    # 切向（垂直方向）不变
    assert p1.vy == 100.0
    assert p2.vy == 50.0
    # 被撞静止方进入飞行
    assert p2.flying


def test_unequal_mass_momentum_relation():
    """不同质量碰撞满足一维动量关系（考虑 e=0.995），分离状态不重复碰撞。"""
    p1 = _pet("big", 0.0, 0.0, vx=1000.0, size=400, flying=True)
    p2 = _pet("small", 380.0, 0.0, vx=0.0, size=200, flying=False)
    m1, m2 = 400.0**2, 200.0**2
    p_before = m1 * 1000.0
    assert collision.resolve_pair_collision(p1, p2)
    p_after = m1 * p1.vx + m2 * p2.vx
    assert math.isclose(p_before, p_after, rel_tol=0.01)
    assert p2.vx > p1.vx  # 小质量被撞得更快
    # 再次调用：相对速度已分离，不重复弹跳
    vx1, vx2 = p1.vx, p2.vx
    assert not collision.resolve_pair_collision(p1, p2)
    assert (p1.vx, p2.vx) == (vx1, vx2)


def test_coincident_centers_skipped():
    """中心重合不抛异常，本帧跳过。"""
    p1 = _pet("a", 100.0, 100.0, vx=500.0, flying=True)
    p2 = _pet("b", 100.0, 100.0)
    assert not collision.resolve_pair_collision(p1, p2)


def test_both_static_or_not_overlapping_ignored():
    """双方都静止时不处理；不相交时不处理。"""
    p1 = _pet("a", 0.0, 0.0)
    p2 = _pet("b", 300.0, 0.0)
    assert not collision.resolve_pair_collision(p1, p2)
    p1.flying = True
    p3 = _pet("c", 5000.0, 0.0, vx=1000.0, flying=True)
    assert not collision.resolve_pair_collision(p1, p3)


def test_resolve_all_pairs():
    """resolve_all_collisions 覆盖全部宠物对；静止被撞方也会飞。"""
    pets = [
        _pet("a", 0.0, 0.0, vx=800.0, flying=True),
        _pet("b", 300.0, 0.0),
        _pet("c", 2000.0, 0.0),
    ]
    collision.resolve_all_collisions(pets)
    assert pets[1].vx > 600.0  # b 被撞飞
    assert pets[1].flying
    assert pets[2].vx == 0.0  # c 不相干
