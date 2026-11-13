"""PetWorld：多宠物统一物理世界，拖拽弹簧、飞行积分、碰撞、心情的统一更新入口（纯 Python，禁 Qt）。"""

from __future__ import annotations

import random
import time
from typing import Callable

from . import collision, physics
from .models import AppSettings, PetConfig, PetState
from .mood import MoodTracker

_SAMPLE_WINDOW_MS = 200  # 拖拽轨迹保留窗口
_CLICK_DELTAS = (-1, 0, 1, 2)  # 单击心情随机浮动候选


class _DragData:
    """单只宠物的拖拽会话数据。"""

    __slots__ = ("offset_x", "offset_y", "target_x", "target_y", "samples")

    def __init__(self, offset_x: float, offset_y: float, x: float, y: float) -> None:
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.target_x = x
        self.target_y = y
        self.samples: list[tuple[int, float, float]] = []


class PetWorld:
    """多宠物逻辑世界：保存全部宠物状态，统一驱动物理、碰撞与心情更新。

    渲染壳（overlay/desktop）共享同一实例；update 由 UI 层以真实时间差调用。
    """

    def __init__(self, settings: AppSettings, clock: Callable[[], float] | None = None) -> None:
        """按配置构建世界。

        :param settings: 应用配置（物理参数、宠物列表、心情设置）。
        :param clock: 毫秒时钟（可注入便于测试），默认 time.monotonic。
        """
        self._settings = settings
        self._pets: list[PetState] = []
        self._moods: dict[str, MoodTracker] = {}
        self._drags: dict[str, _DragData] = {}
        self._bounds: tuple[float, float, float, float] = (0.0, 0.0, 1920.0, 1080.0)
        self._clock_ms: Callable[[], int] = (
            (lambda: int(clock() * 1000)) if clock else (lambda: int(time.monotonic() * 1000))
        )

    @property
    def pets(self) -> list[PetState]:
        """当前全部宠物状态列表（勿外部增删）。"""
        return self._pets

    @property
    def physics_params(self):
        """当前物理参数（AppSettings.physics）。"""
        return self._settings.physics

    @property
    def mood_settings(self):
        """当前心情参数（AppSettings.mood），UI 展示增益数值用。"""
        return self._settings.mood

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """当前世界边界 (left, top, right, bottom)。"""
        return self._bounds

    def get_pet(self, pet_id: str) -> PetState:
        """按 id 取宠物状态。

        :raises KeyError: pet_id 不存在。
        """
        for pet in self._pets:
            if pet.pet_id == pet_id:
                return pet
        raise KeyError(f"宠物不存在: {pet_id}")

    def mood_tracker(self, pet_id: str) -> MoodTracker:
        """按 id 取心情跟踪器。

        :raises KeyError: pet_id 不存在。
        """
        return self._moods[pet_id]

    def _default_position(self, config: PetConfig) -> tuple[float, float]:
        """默认位置：主屏右下角，约 24px 横向 / 100px 纵向边距；多宠向左错开。"""
        left, top, right, bottom = self._bounds
        height = config.size * 9 / 16
        index = len(self._pets)
        x = right - config.size - 24.0 - index * (config.size + 40.0)
        y = bottom - height - 100.0
        return max(left, x), max(top, y)

    def _position_visible(self, x: float, y: float, size: int) -> bool:
        """位置是否至少有部分可见于当前边界。"""
        height = size * 9 / 16
        left, top, right, bottom = self._bounds
        return x + size > left and x < right and y + height > top and y < bottom

    def add_pet(self, config: PetConfig) -> PetState:
        """按配置添加一只宠物。

        :param config: 宠物配置（id 须唯一）。
        :return: 新建的 PetState。
        :raises ValueError: id 已存在。
        """
        if any(p.pet_id == config.id for p in self._pets):
            raise ValueError(f"宠物 id 重复: {config.id}")
        x, y = config.x, config.y
        if x is None or y is None or not self._position_visible(x, y, config.size):
            x, y = self._default_position(config)
        pet = PetState(pet_id=config.id, x=float(x), y=float(y), size=config.size)
        self._pets.append(pet)
        self._moods[config.id] = MoodTracker(self._settings.mood)
        return pet

    def remove_pet(self, pet_id: str) -> None:
        """移除指定宠物；不存在时静默忽略。"""
        self._pets = [p for p in self._pets if p.pet_id != pet_id]
        self._moods.pop(pet_id, None)
        self._drags.pop(pet_id, None)

    def set_bounds(self, rect: tuple[float, float, float, float]) -> None:
        """设置世界边界 (left, top, right, bottom)（虚拟桌面可用区）。"""
        self._bounds = rect

    def update(self, dt: float) -> None:
        """统一推进一帧：心情衰减、拖拽弹簧、飞行积分（含细分）、多宠物碰撞。

        :param dt: 距上次调用的真实时间差（秒），内部按 physics.clamp_dt 钳制。
        """
        dt = physics.clamp_dt(dt)
        params = self._settings.physics
        for pet in self._pets:
            self._moods[pet.pet_id].update(dt)
            drag = self._drags.get(pet.pet_id)
            if drag is not None:
                pet.x, pet.vx = physics.spring_step(pet.x, pet.vx, drag.target_x, dt)
                pet.y, pet.vy = physics.spring_step(pet.y, pet.vy, drag.target_y, dt)
                self._moods[pet.pet_id].on_drag(dt)
                self._trim_samples(drag)
            elif pet.flying:
                pet.x, pet.y, pet.vx, pet.vy, pet.flying = physics.integrate_flight(
                    pet.x, pet.y, pet.vx, pet.vy, dt, params, self._bounds, pet.size
                )
        if params.pet_collision:
            collision.resolve_all_collisions(self._pets)

    def pet_at(self, x: float, y: float) -> PetState | None:
        """命中测试：返回包围盒包含该点的最上层宠物；未命中为 None。"""
        for pet in reversed(self._pets):
            px, py, w, h = pet.rect
            if px <= x < px + w and py <= y < py + h:
                return pet
        return None

    def start_drag(self, pet_id: str, px: float, py: float) -> None:
        """开始拖拽：记录指针偏移并清空轨迹采样。

        :raises KeyError: pet_id 不存在。
        """
        pet = self.get_pet(pet_id)
        pet.dragging = True
        pet.flying = False
        pet.vx = pet.vy = 0.0
        drag = _DragData(px - pet.x, py - pet.y, pet.x, pet.y)
        drag.samples.append((self._clock_ms(), px, py))
        self._drags[pet_id] = drag

    def drag_to(self, pet_id: str, px: float, py: float) -> None:
        """拖拽移动：更新弹簧目标并追加轨迹样本。

        :raises KeyError: pet_id 不存在或不在拖拽中。
        """
        drag = self._drags.get(pet_id)
        if drag is None:
            raise KeyError(f"宠物不在拖拽中: {pet_id}")
        drag.target_x = px - drag.offset_x
        drag.target_y = py - drag.offset_y
        drag.samples.append((self._clock_ms(), px, py))
        self._trim_samples(drag)

    def end_drag(self, pet_id: str) -> None:
        """结束拖拽：按轨迹估算初速，进入飞行或温柔放下。

        :raises KeyError: pet_id 不存在。
        """
        pet = self.get_pet(pet_id)
        drag = self._drags.pop(pet_id, None)
        pet.dragging = False
        if drag is None:
            return
        vx, vy = physics.estimate_throw_velocity(
            drag.samples, self._settings.physics.throw_power, self._clock_ms()
        )
        if vx != 0.0 or vy != 0.0:
            pet.vx, pet.vy = vx, vy
            pet.flying = True
            self._moods[pet_id].on_throw()
        else:
            pet.vx = pet.vy = 0.0
            pet.flying = False

    def click_pet(self, pet_id: str) -> str:
        """点击宠物：心情随机浮动 [-1, 0, 1, 2] 并返回变化后的档位名。

        :raises KeyError: pet_id 不存在。
        """
        delta = random.choice(_CLICK_DELTAS)
        return self._moods[pet_id].apply_delta(delta)

    def _trim_samples(self, drag: _DragData) -> None:
        """丢弃 200ms 窗口之外的轨迹样本。"""
        now = self._clock_ms()
        drag.samples = [s for s in drag.samples if now - s[0] <= _SAMPLE_WINDOW_MS]
