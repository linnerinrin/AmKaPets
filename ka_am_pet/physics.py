"""纯 Python 甩抛物理：拖拽弹簧、松手初速估算、飞行积分与边界（禁 Qt，可单测）。"""

from __future__ import annotations

import math

from .models import PhysicsParams

SPRING_K = 200.0
SPRING_C = 30.0
MAX_DT = 0.05
SUBSTEP_MAX_PX = 8.0
SUBSTEP_MAX_COUNT = 64
SOFT_LIMIT = 3600.0
MIN_THROW_SPEED = 500.0
ACCEL_REF = 8000.0

_SAMPLE_WINDOW_MS = 200      # 轨迹保留窗口
_ESTIMATE_WINDOW_MS = 150    # 初速估算窗口
_MIN_SPAN_MS = 20            # 估算窗口最短跨度
_SEGMENT_MIN_MS = 8          # 分段采样最小 dt
_MAX_ACCEL_GAIN = 0.6        # 末段加速增益上限


def soft_clamp(speed: float, limit: float = SOFT_LIMIT) -> float:
    """软限速：单调递增、渐近不超过 limit。

    :param speed: 输入速率（px/s）。
    :param limit: 软上限，默认 3600。
    :return: 限速后的速率。
    """
    if speed <= 0:
        return 0.0
    return limit * (1.0 - math.exp(-speed / limit))


def clamp_dt(dt: float) -> float:
    """将帧时间差钳制到 [0, MAX_DT]。

    :param dt: 真实时间差（秒）。
    :return: 钳制后的时间差。
    """
    return min(max(dt, 0.0), MAX_DT)


def spring_step(x: float, v: float, target: float, dt: float, power: float = 1.0) -> tuple[float, float]:
    """过阻尼弹簧单步：拖拽跟手。

    v += ((target - x) * SPRING_K - v * SPRING_C) * power * dt；x += v * dt。

    :param x: 当前位置（某轴）。
    :param v: 当前速度（某轴）。
    :param target: 弹簧目标位置（指针位置 - 偏移）。
    :param dt: 时间步（秒）。
    :param power: 力度系数，默认 1.0。
    :return: (新位置, 新速度)。
    """
    dt = clamp_dt(dt)
    v += ((target - x) * SPRING_K - v * SPRING_C) * power * dt
    x += v * dt
    return x, v


def _merged_segments(samples: list[tuple[int, float, float]]) -> list[tuple[float, float, float]]:
    """把过密样本向前合并成分段速度 [(dt_s, vx, vy), ...]，分段最小 dt 8ms。"""
    segments: list[tuple[float, float, float]] = []
    if len(samples) < 2:
        return segments
    seg_start = samples[0]
    acc_t = 0.0
    acc_dx = 0.0
    acc_dy = 0.0
    for i in range(1, len(samples)):
        t0, x0, y0 = samples[i - 1]
        t1, x1, y1 = samples[i]
        acc_t += (t1 - t0) / 1000.0
        acc_dx += x1 - x0
        acc_dy += y1 - y0
        if acc_t * 1000.0 >= _SEGMENT_MIN_MS:
            if acc_t > 0:
                segments.append((acc_t, acc_dx / acc_t, acc_dy / acc_t))
            acc_t = acc_dx = acc_dy = 0.0
    # 末尾不足 8ms 的残余并入最后一段（没有则丢弃）
    if acc_t > 0 and segments:
        dt, vx, vy = segments[-1]
        total = dt + acc_t
        segments[-1] = (total, (vx * dt + acc_dx) / total, (vy * dt + acc_dy) / total)
    return segments


def estimate_throw_velocity(
    samples: list[tuple[int, float, float]],
    throw_power: float = 1.0,
    now_ms: int | None = None,
) -> tuple[float, float]:
    """松手初速估算。

    规则：最后样本距松手超 150ms 温柔放下清零；窗口取最近 150ms，不足 20ms 原地放下；
    speed = 0.5*端点平均 + 0.5*分段峰值（分段最小 dt 8ms）；末段加速增益最多 60%
    （accel_ref=8000）；soft_clamp 软限速；乘 throw_power；低于 500px/s 不抛。
    方向使用端点平均速度方向；方向长度近零时原地放下。

    :param samples: 最近 200ms 指针轨迹 [(t_ms, x, y), ...]，按时间升序。
    :param throw_power: 抛掷力度系数。
    :param now_ms: 松手时刻（毫秒）；None 时取最后样本时间。
    :return: (vx, vy)，px/s；不抛时返回 (0, 0)。
    """
    if not samples:
        return 0.0, 0.0
    if now_ms is None:
        now_ms = samples[-1][0]
    if now_ms - samples[-1][0] > _ESTIMATE_WINDOW_MS:
        return 0.0, 0.0

    window = [s for s in samples if now_ms - s[0] <= _ESTIMATE_WINDOW_MS]
    if len(window) < 2:
        return 0.0, 0.0
    t0, x0, y0 = window[0]
    t1, x1, y1 = window[-1]
    span = (t1 - t0) / 1000.0
    if span * 1000.0 < _MIN_SPAN_MS:
        return 0.0, 0.0

    base_vx = (x1 - x0) / span
    base_vy = (y1 - y0) / span
    base_speed = math.hypot(base_vx, base_vy)

    segments = _merged_segments(window)
    peak_speed = max((math.hypot(vx, vy) for _, vx, vy in segments), default=0.0)

    speed = 0.5 * base_speed + 0.5 * peak_speed

    # 末段仍在加速：增益最多 60%
    if len(segments) >= 2:
        dt_a, vxa, vya = segments[-2]
        dt_b, vxb, vyb = segments[-1]
        dt_mid = dt_a / 2.0 + dt_b / 2.0
        if dt_mid > 0:
            accel = (math.hypot(vxb, vyb) - math.hypot(vxa, vya)) / dt_mid
            if accel > 0:
                speed *= 1.0 + min(_MAX_ACCEL_GAIN, accel / ACCEL_REF * _MAX_ACCEL_GAIN)

    speed = soft_clamp(speed) * throw_power
    if speed < MIN_THROW_SPEED:
        return 0.0, 0.0
    if base_speed < 1e-6:
        return 0.0, 0.0
    return base_vx / base_speed * speed, base_vy / base_speed * speed


def integrate_flight(
    x: float,
    y: float,
    vx: float,
    vy: float,
    dt: float,
    params: PhysicsParams,
    bounds: tuple[float, float, float, float],
    size: int,
) -> tuple[float, float, float, float, bool]:
    """飞行积分一步（含 8px 细分，最多 64 子步）与边界反弹/摩擦/停止判定。

    重力 vy += gravity*dt；左右越界夹回反弹；顶部按 ceiling_bounce 处理；
    落地摩擦与静止判定（|vy|<40 清零，|vx|<15 且 |vy|<1 停止飞行）。

    :param x, y: 包围盒左上角坐标。
    :param vx, vy: 速度（px/s）。
    :param dt: 帧时间差（秒），内部 clamp_dt。
    :param params: 物理参数。
    :param bounds: (left, top, right, bottom) 可用区域。
    :param size: 宠物尺寸（推导高度 size*9/16）。
    :return: (x, y, vx, vy, still_flying)。
    """
    dt = clamp_dt(dt)
    if dt <= 0.0:
        return x, y, vx, vy, True

    left, top, right, bottom = bounds
    height = size * 9 / 16
    max_x = right - size
    max_y = bottom - height

    travel = math.hypot(vx * dt, vy * dt)
    steps = min(SUBSTEP_MAX_COUNT, max(1, math.ceil(travel / SUBSTEP_MAX_PX)))
    sub_dt = dt / steps

    for _ in range(steps):
        vy += params.gravity * sub_dt
        x += vx * sub_dt
        y += vy * sub_dt

        if x < left:
            x = left
            vx = abs(vx) * params.restitution
        elif x > max_x:
            x = max_x
            vx = -abs(vx) * params.restitution

        if y < top:
            if params.ceiling_bounce:
                y = top
                vy = abs(vy) * params.restitution
            # 否则允许飞出，靠重力落回
        elif y >= max_y:
            y = max_y
            vx *= max(0.0, 1.0 - params.ground_friction * sub_dt)
            if abs(vy) < 40.0:
                vy = 0.0
            else:
                vy = -abs(vy) * params.restitution

    on_ground = y >= max_y
    if on_ground and abs(vy) < 1.0 and abs(vx) < 15.0:
        return x, y, 0.0, 0.0, False
    return x, y, vx, vy, True
