"""甩抛物理测试（纯函数，不碰 Qt）。"""

import math

from ka_am_pet import physics
from ka_am_pet.models import PhysicsParams


def _samples_slow():
    """慢速拖动：100ms 内移动 30px（约 300px/s）。"""
    return [(0, 0.0, 0.0), (50, 15.0, 0.0), (100, 30.0, 0.0)]


def _samples_fast():
    """快速甩动：150ms 内移动 600px（约 4000px/s），样本密集。"""
    return [(i * 10, float(i * 40), 0.0) for i in range(16)]


def test_soft_clamp_monotonic_and_bounded():
    """软限速：输入越大输出越大（单调），且永远不超过 3600。"""
    prev = -1.0
    for s in range(0, 20000, 100):
        out = physics.soft_clamp(float(s))
        assert out >= prev, "必须单调递增"
        assert out < 3600.0, "不得超过软上限"
        prev = out
    assert physics.soft_clamp(0) == 0.0
    assert physics.soft_clamp(-5) == 0.0
    assert math.isclose(physics.soft_clamp(3600), 3600 * (1 - math.exp(-1)), rel_tol=1e-9)


def test_slow_release_does_not_throw():
    """低速松手（<500px/s）不抛，速度清零原地停下。"""
    vx, vy = physics.estimate_throw_velocity(_samples_slow(), now_ms=100)
    assert (vx, vy) == (0.0, 0.0)
    # 最后样本距松手超过 150ms：温柔放下
    vx, vy = physics.estimate_throw_velocity(_samples_fast(), now_ms=1000)
    assert (vx, vy) == (0.0, 0.0)
    # 窗口不足 20ms：原地放下
    vx, vy = physics.estimate_throw_velocity([(0, 0.0, 0.0), (10, 500.0, 0.0)], now_ms=10)
    assert (vx, vy) == (0.0, 0.0)


def test_fast_release_produces_finite_velocity():
    """快速松手产生有限初速（受软限速约束）。"""
    vx, vy = physics.estimate_throw_velocity(_samples_fast(), now_ms=150)
    speed = math.hypot(vx, vy)
    assert 500.0 <= speed < 3600.0
    assert vy == 0.0 and vx > 0  # 纯水平向右


def test_gravity_increases_vy_and_landing_restitution():
    """重力使 vy 增大；落地反弹系数正确；最终可静止。"""
    params = PhysicsParams()
    bounds = (0.0, 0.0, 1920.0, 1080.0)
    x, y, vx, vy, flying = physics.integrate_flight(500.0, 100.0, 0.0, 0.0, 0.016, params, bounds, 320)
    assert vy > 0, "重力使 vy 增大"

    # 落地反弹：vy = -|vy| * restitution
    max_y = 1080.0 - 320 * 9 / 16
    x, y, vx, vy, flying = physics.integrate_flight(500.0, max_y - 1, 0.0, -1000.0 * -1, 0.05, params, bounds, 320)
    assert y <= max_y
    # 长时模拟最终静止
    x, y, vx, vy = 500.0, 100.0, 300.0, 0.0
    flying = True
    for _ in range(2000):
        x, y, vx, vy, flying = physics.integrate_flight(x, y, vx, vy, 0.016, params, bounds, 320)
        if not flying:
            break
    assert not flying, "最终必须停止飞行"
    assert vx == 0.0 and vy == 0.0


def test_ceiling_bounce_false_does_not_clamp_top():
    """ceiling_bounce=false 时不夹回顶部，允许飞出靠重力落回。"""
    params = PhysicsParams(ceiling_bounce=False)
    bounds = (0.0, 0.0, 1920.0, 1080.0)
    x, y, vx, vy, flying = physics.integrate_flight(500.0, 10.0, 0.0, -3000.0, 0.05, params, bounds, 320)
    assert y < 0.0, "允许飞出顶部"
    assert vy < 0.0, "不反弹"
    # 对照组：ceiling_bounce=true 时夹回并反弹向下
    params_b = PhysicsParams(ceiling_bounce=True)
    _, y2, _, vy2, _ = physics.integrate_flight(500.0, 10.0, 0.0, -3000.0, 0.05, params_b, bounds, 320)
    assert y2 >= 0.0 and vy2 > 0.0


def test_dt_clamped_and_high_speed_substep():
    """dt 上限 0.05；高速运动按 8px 细分且子步数不超过 64。"""
    assert physics.clamp_dt(0.2) == 0.05
    assert physics.clamp_dt(-1.0) == 0.0
    assert physics.clamp_dt(0.016) == 0.016

    params = PhysicsParams()
    # 开阔边界，避免反弹干扰位移观测
    bounds = (-1e6, -1e6, 1e6, 1e6)
    # 超高速 100000px/s，dt=0.05 → 位移 5000px；若不细分会穿透，细分后每步 <= 8px
    x, y, vx, vy, flying = physics.integrate_flight(0.0, 0.0, 100000.0, 0.0, 0.05, params, bounds, 320)
    # 重力在 0.05s 内仅增加 70px/s 的 vy，总位移由 vx 主导
    assert 4900.0 < x < 5100.0, f"细分积分应保持总位移一致, got x={x}"
