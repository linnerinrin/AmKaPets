"""PetWorld 主类：多宠物统一物理世界。

统一驱动心情衰减、拖拽弹簧、飞行积分（含细分）与多宠物碰撞；
渲染壳（overlay/desktop）共享同一实例，由 UI 层以真实时间差调用 ``update``。

辅助类型、落位纯函数、交互 mixin、事件类型分别位于
``runtime.py`` / ``placement.py`` / ``interaction.py`` / ``events.py``。
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Callable

from .. import collision, physics
from ..actions import CLICK_COOLDOWN_SECONDS, PAT_ACTIONS
from ..models import (
    AppSettings,
    AudioSettings,
    MoodSettings,
    PetConfig,
    PetOverrides,
    PetState,
    PhysicsParams,
)
from ..mood import ClickCounter, MoodTracker
from .events import KIND_DRAG, KIND_FLIGHT, MoodEvent
from .interaction import InteractionMixin
from .placement import default_position, pet_at as _hit_pet_at, position_visible
from .runtime import SAMPLE_WINDOW_MS, DragData, PetRuntimeSettings


class PetWorld(InteractionMixin):
    """多宠物逻辑世界：保存全部宠物状态，统一驱动物理、碰撞与心情更新。

    每只宠物自带一份完整设置组（物理 / 律动），好感数值则是全局常量；
    ``_resolved`` 缓存生效设置，设置保存后调用 :meth:`refresh_settings` 重建即可热生效。
    """

    def __init__(self, settings: AppSettings, clock: Callable[[], float] | None = None) -> None:
        """按配置构建世界。

        :param settings: 应用配置（默认物理参数、宠物列表、心情提示词）。
        :param clock: 秒级时钟（可注入便于测试），默认 time.monotonic。
        """
        self._settings = settings
        self._pets: list[PetState] = []
        self._moods: dict[str, MoodTracker] = {}
        self._clicks: dict[str, ClickCounter] = {}
        self._pats: dict[str, ClickCounter] = {}
        self._drags: dict[str, DragData] = {}
        self._overrides: dict[str, PetOverrides] = {}
        self._resolved: dict[str, PetRuntimeSettings] = {}
        self._events: list[MoodEvent] = []
        self._drag_delta: dict[str, int] = {}
        self._flight_delta: dict[str, int] = {}
        self._bounds: tuple[float, float, float, float] = (0.0, 0.0, 1920.0, 1080.0)
        self._clock_ms: Callable[[], int] = (
            (lambda: int(clock() * 1000)) if clock else (lambda: int(time.monotonic() * 1000))
        )

    # ---- 只读属性 ----

    @property
    def pets(self) -> list[PetState]:
        """当前全部宠物状态列表（勿外部增删）。"""
        return self._pets

    @property
    def physics_params(self) -> PhysicsParams:
        """默认物理参数（AppSettings.physics，新建实例时用）。"""
        return self._settings.physics

    @property
    def mood_settings(self) -> MoodSettings:
        """好感设置（数值是常量，只有四档提示词可改）。"""
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

    # ---- 实例设置 ----

    def default_overrides(self) -> PetOverrides:
        """新建实例的默认设置组（取 AppSettings 的全局默认值）。"""
        return PetOverrides(
            physics=replace(self._settings.physics),
            chat=replace(self._settings.chat),
            music=replace(self._settings.audio),
        )

    def _resolve(self, pet_id: str) -> PetRuntimeSettings:
        overrides = self._overrides.get(pet_id) or self.default_overrides()
        mood = replace(self._settings.mood, prompts=dict(self._settings.mood.prompts))
        return PetRuntimeSettings(
            physics=replace(overrides.physics),
            audio=replace(overrides.music),
            mood=mood,
        )

    def physics_for(self, pet_id: str) -> PhysicsParams:
        """某只宠物实际生效的物理参数。"""
        return self._resolved[pet_id].physics

    def audio_for(self, pet_id: str) -> AudioSettings:
        """某只宠物实际生效的音乐律动设置。"""
        return self._resolved[pet_id].audio

    def mood_settings_for(self, pet_id: str) -> MoodSettings:
        """某只宠物实际生效的好感设置。"""
        return self._resolved[pet_id].mood

    def overrides_for(self, pet_id: str) -> PetOverrides:
        """某只宠物的设置组（只读语义，勿直接改后不刷新缓存）。"""
        return self._overrides.get(pet_id) or self.default_overrides()

    def pat_pool_for(self, pet_id: str) -> tuple[str, ...]:
        """该实例的摸头（双击）动作池；空池回退默认动作池（动作 1）。"""
        return self.overrides_for(pet_id).pat_pool or PAT_ACTIONS

    def set_overrides(self, pet_id: str, overrides: PetOverrides) -> None:
        """替换某只宠物的设置组并热更新缓存/心情跟踪器。"""
        if pet_id not in self._resolved:
            raise KeyError(f"宠物不存在: {pet_id}")
        self._overrides[pet_id] = overrides
        self._apply_runtime(pet_id)

    def refresh_settings(self) -> None:
        """全局默认值或提示词变化后重建全部解析缓存。"""
        for pet in self._pets:
            self._apply_runtime(pet.pet_id)

    def _apply_runtime(self, pet_id: str) -> None:
        runtime = self._resolve(pet_id)
        self._resolved[pet_id] = runtime
        tracker = self._moods.get(pet_id)
        if tracker is not None and not tracker.practice:
            tracker.set_settings(runtime.mood)

    def set_passthrough(self, pet_id: str, passthrough: bool) -> None:
        """设置某只宠物的覆盖模式（只看得见、点不到）。"""
        self.get_pet(pet_id).passthrough = bool(passthrough)

    # ---- 直播练习 ----

    def practice_on(self, pet_id: str) -> bool:
        """该宠物是否处于直播练习（好感冻结在 100）。"""
        tracker = self._moods.get(pet_id)
        return bool(tracker is not None and tracker.practice)

    def set_practice(self, pet_id: str, on: bool) -> None:
        """切换直播练习：进入钉在 100，退出恢复进入前的值（见 mood.MoodTracker）。"""
        self._moods[pet_id].set_practice(on)

    # ---- 位置与生命周期 ----

    def add_pet(
        self,
        config: PetConfig,
        overrides: PetOverrides | None = None,
        passthrough: bool = False,
    ) -> PetState:
        """按配置添加一只宠物。

        :param config: 宠物配置（id 须唯一）。
        :param overrides: 实例设置组；None 用 AppSettings 的默认值。
        :param passthrough: 是否以覆盖模式（点不到）启动。
        :return: 新建的 PetState。
        :raises ValueError: id 已存在。
        """
        if any(p.pet_id == config.id for p in self._pets):
            raise ValueError(f"宠物 id 重复: {config.id}")
        x, y = config.x, config.y
        if x is None or y is None or not position_visible(self._bounds, x, y, config.size):
            x, y = default_position(self._bounds, config.size, len(self._pets))
        pet = PetState(pet_id=config.id, x=float(x), y=float(y), size=config.size, passthrough=passthrough)
        self._pets.append(pet)
        self._overrides[config.id] = overrides or self.default_overrides()
        self._resolved[config.id] = self._resolve(config.id)
        self._moods[config.id] = MoodTracker(self._resolved[config.id].mood)
        self._clicks[config.id] = ClickCounter(cooldown=CLICK_COOLDOWN_SECONDS)
        self._pats[config.id] = ClickCounter(every=1, cooldown=CLICK_COOLDOWN_SECONDS)
        return pet

    def remove_pet(self, pet_id: str) -> None:
        """移除指定宠物；不存在时静默忽略。"""
        self._pets = [p for p in self._pets if p.pet_id != pet_id]
        for store in (self._moods, self._clicks, self._pats, self._drags, self._overrides, self._resolved):
            store.pop(pet_id, None)
        self._drag_delta.pop(pet_id, None)
        self._flight_delta.pop(pet_id, None)

    def set_bounds(self, rect: tuple[float, float, float, float]) -> None:
        """设置世界边界 (left, top, right, bottom)（虚拟桌面可用区）。"""
        self._bounds = rect

    # ---- 每帧更新 ----

    def update(self, dt: float) -> None:
        """统一推进一帧：心情衰减、拖拽弹簧、飞行积分（含细分）、多宠物碰撞。

        :param dt: 距上次调用的真实时间差（秒），内部按 physics.clamp_dt 钳制。
        """
        dt = physics.clamp_dt(dt)
        for pet in self._pets:
            runtime = self._resolved[pet.pet_id]
            tracker = self._moods[pet.pet_id]
            tracker.update(dt)
            drag = self._drags.get(pet.pet_id)
            if drag is not None:
                pet.x, pet.vx = physics.spring_step(pet.x, pet.vx, drag.target_x, dt)
                pet.y, pet.vy = physics.spring_step(pet.y, pet.vy, drag.target_y, dt)
                self._drag_delta[pet.pet_id] = self._drag_delta.get(pet.pet_id, 0) + tracker.on_drag(dt)
                self.trim_samples(drag)
            elif pet.flying:
                was_flying = pet.flying
                pet.x, pet.y, pet.vx, pet.vy, pet.flying = physics.integrate_flight(
                    pet.x, pet.y, pet.vx, pet.vy, dt, runtime.physics, self._bounds, pet.size
                )
                self._flight_delta[pet.pet_id] = self._flight_delta.get(pet.pet_id, 0) + tracker.on_flight(dt)
                if was_flying and not pet.flying:
                    self.flush_mood_event(pet.pet_id, KIND_FLIGHT)
        collidable = [p for p in self._pets if self._resolved[p.pet_id].physics.pet_collision]
        if len(collidable) > 1:
            collision.resolve_all_collisions(collidable)

    # ---- 事件 ----

    def flush_mood_event(self, pet_id: str, kind: str) -> None:
        """把某只宠物累积的拖拽/飞行好感增量结算成一条事件。

        增量为 0 时不发事件：用户只要看到「提起 +2 → 82」这种真有涨的飘字，
        显示「+0」只会变成噪音。
        """
        store = self._drag_delta if kind == KIND_DRAG else self._flight_delta
        delta = store.pop(pet_id, 0)
        if delta <= 0:
            return
        tracker = self._moods.get(pet_id)
        value = tracker.value if tracker is not None else 0.0
        self._events.append(MoodEvent(pet_id=pet_id, kind=kind, delta=delta, value=value))

    def drain_events(self) -> list[MoodEvent]:
        """取走并清空待展示的结算事件（壳层每帧调用一次）。"""
        events = self._events
        self._events = []
        return events

    # ---- 命中测试 ----

    def pet_at(self, x: float, y: float) -> PetState | None:
        """命中测试：返回包围盒包含该点的最上层「可交互」宠物；未命中为 None。"""
        return _hit_pet_at(self._pets, x, y)


__all__ = ["PetWorld", "SAMPLE_WINDOW_MS"]
