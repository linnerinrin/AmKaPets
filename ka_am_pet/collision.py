"""纯 Python 多宠物碰撞解析（禁止 import Qt，保证可单测）。

碰撞规则：
- 质量 m = size ** 2。
- 碰撞法向为两宠物包围盒中心连线；中心重合时跳过本帧，避免除零。
- 仅当至少一方处于飞行状态时处理；被撞静止方获得速度并进入飞行状态。
- 相对速度法向投影 vrel <= 0 表示正在分离，不重复弹跳。
- 恢复系数默认 e = 0.995，法向速度按一维动量公式重分配，切向速度保持不变。
"""

from __future__ import annotations

import math

from .models import PetState

DEFAULT_RESTITUTION = 0.995


def _center(p: PetState) -> tuple[float, float]:
    return p.x + p.width / 2.0, p.y + p.height / 2.0


def _rects_overlap(p1: PetState, p2: PetState) -> bool:
    return (
        p1.x < p2.x + p2.width
        and p2.x < p1.x + p1.width
        and p1.y < p2.y + p2.height
        and p2.y < p1.y + p1.height
    )


def resolve_pair_collision(p1: PetState, p2: PetState, restitution: float = DEFAULT_RESTITUTION) -> bool:
    """解析一对宠物之间的碰撞。

    法向速度重分配::

        v1n2 = ((m1 - e*m2)*v1n + (1+e)*m2*v2n) / (m1 + m2)
        v2n2 = ((m2 - e*m1)*v2n + (1+e)*m1*v1n) / (m1 + m2)

    :param p1: 第一只宠物状态，可能被就地修改速度/飞行标志。
    :param p2: 第二只宠物状态，可能被就地修改速度/飞行标志。
    :param restitution: 恢复系数 e，默认 0.995。
    :return: 本帧是否实际发生了碰撞解析（发生了速度重分配）。
    """
    if not (p1.flying or p2.flying):
        return False
    if not _rects_overlap(p1, p2):
        return False

    c1x, c1y = _center(p1)
    c2x, c2y = _center(p2)
    nx = c2x - c1x
    ny = c2y - c1y
    dist = math.hypot(nx, ny)
    if dist < 1e-9:
        return False  # 中心重合，跳过本帧
    nx /= dist
    ny /= dist

    # 相对速度法向投影：vrel <= 0 表示正在分离
    vrel = (p1.vx - p2.vx) * nx + (p1.vy - p2.vy) * ny
    if vrel <= 0:
        return False

    m1 = float(p1.size ** 2)
    m2 = float(p2.size ** 2)
    e = restitution

    v1n = p1.vx * nx + p1.vy * ny
    v2n = p2.vx * nx + p2.vy * ny

    v1n2 = ((m1 - e * m2) * v1n + (1 + e) * m2 * v2n) / (m1 + m2)
    v2n2 = ((m2 - e * m1) * v2n + (1 + e) * m1 * v1n) / (m1 + m2)

    # 切向速度不变：最终速度 = 原切向分量 + 新法向分量
    p1.vx += (v1n2 - v1n) * nx
    p1.vy += (v1n2 - v1n) * ny
    p2.vx += (v2n2 - v2n) * nx
    p2.vy += (v2n2 - v2n) * ny

    # 被撞静止方获得速度并进入飞行状态
    if math.hypot(p1.vx, p1.vy) > 1.0:
        p1.flying = True
    if math.hypot(p2.vx, p2.vy) > 1.0:
        p2.flying = True

    # 位置分离：把重叠深度沿法向按质量反比推开，避免连续帧粘连
    overlap_x = min(p1.x + p1.width, p2.x + p2.width) - max(p1.x, p2.x)
    overlap_y = min(p1.y + p1.height, p2.y + p2.height) - max(p1.y, p2.y)
    depth = min(overlap_x, overlap_y)
    total = m1 + m2
    p1.x -= nx * depth * (m2 / total)
    p1.y -= ny * depth * (m2 / total)
    p2.x += nx * depth * (m1 / total)
    p2.y += ny * depth * (m1 / total)
    return True


def resolve_all_collisions(pets: list[PetState], restitution: float = DEFAULT_RESTITUTION) -> None:
    """对全部宠物两两做碰撞解析，同一对宠物同帧只处理一次。

    :param pets: 当前所有宠物状态列表，可能被就地修改。
    :param restitution: 恢复系数 e，默认 0.995。
    """
    for i in range(len(pets)):
        for j in range(i + 1, len(pets)):
            resolve_pair_collision(pets[i], pets[j], restitution)
