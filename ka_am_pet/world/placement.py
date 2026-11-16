"""宠物落位与命中测试纯函数：默认位置计算、可见性判定、点击命中（无状态，便于单测）。

坐标系约定见 AGENTS.md 第 5 节：位置为宠物包围盒左上角，y 向下；
宠物高度 ``h = size * 9 / 16``（16:9 资源）。
"""

from __future__ import annotations

from typing import Iterable

#: 默认落位的右/下边距（像素），AGENTS.md 第 8 节要求约 24px 横向、100px 纵向
_DEFAULT_MARGIN_X = 24.0
_DEFAULT_MARGIN_Y = 100.0
#: 多只宠物同屏时依次向左错开的额外间隔（像素）
_STACK_GAP = 40.0


def default_position(
    bounds: tuple[float, float, float, float],
    size: int,
    index: int,
) -> tuple[float, float]:
    """计算默认位置：边界右下角，多宠向左依次错开。

    :param bounds: 世界边界 (left, top, right, bottom)。
    :param size: 宠物宽度（像素）。
    :param index: 已存在宠物数量，用于错开摆放。
    :return: (x, y)，保证不越出左上边界。
    """
    left, top, right, bottom = bounds
    height = size * 9 / 16
    x = right - size - _DEFAULT_MARGIN_X - index * (size + _STACK_GAP)
    y = bottom - height - _DEFAULT_MARGIN_Y
    return max(left, x), max(top, y)


def position_visible(
    bounds: tuple[float, float, float, float],
    x: float,
    y: float,
    size: int,
) -> bool:
    """判断宠物在该位置是否至少有部分可见于世界边界内。"""
    height = size * 9 / 16
    left, top, right, bottom = bounds
    return x + size > left and x < right and y + height > top and y < bottom


def pet_at(pets: Iterable, x: float, y: float):
    """命中测试：返回包围盒包含 (x, y) 的最上层「可交互」宠物。

    :param pets: PetState 列表，绘制顺序即列表顺序（后者在上层）。
    :return: 命中的宠物；passthrough（只看得见点不到）跳过；未命中返回 None。
    """
    for pet in reversed(list(pets)):
        if pet.passthrough:
            continue
        px, py, w, h = pet.rect
        if px <= x < px + w and py <= y < py + h:
            return pet
    return None
