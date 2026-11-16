"""动作与飘字状态机 mixin：拉伸/镜像翻转/心情飘字的每帧推进。

职责：把 actions.py 的动作规格变成随时间演进的内部状态（拉伸幅度、
翻转进度、飘字队列），并提供给渲染层读取的当前缩放系数。
本模块只依赖 world/actions 接口，不做任何绘制（绘制在 rendering.py）。
"""

from __future__ import annotations

import random
import time

from ka_am_pet import actions
from ka_am_pet.ui.pet_widget import constants as C


class PetAnimationMixin:
    """动作状态机：统一播放入口 + 每帧推进（由 PetWidget 组合使用）。"""

    # ---- 心情飘字 ----

    def _push_popup(self, text: str) -> None:
        """追加一条飘字（超出上限时丢掉最旧的）。"""
        self._popups.append((text, time.monotonic()))
        if len(self._popups) > C.POPUP_MAX:
            del self._popups[:-C.POPUP_MAX]

    # ---- 动作（统一入口） ----

    def play_action(
        self, spec: str | actions.ActionSpec, *, with_popup: str | None = None
    ) -> None:
        """按 actions.py 的动作定义播放一个动作。

        :param spec: 动作 key（nod / sway / pat）或 :class:`actions.ActionSpec`。
            两种都接受：actions 里的随机/映射函数返回的是规格对象，如果这里只认
            key，传进来会被 :func:`actions.action` 静默回退成点头摇摆——曾因此让
            「听音乐摇摆动作」怎么写都只点头。
        :param with_popup: 顺带飘出的文字（None 表示不飘字）。
        """
        resolved = spec if isinstance(spec, actions.ActionSpec) else actions.action(spec)
        if resolved.kind == "flip":
            self._start_flip_run(max(1, resolved.flips))
        else:
            # stretch（点头拉伸）与 squish（摸头压扁）共用一条时间轴，渲染曲线不同
            self._stretch_kind = resolved.kind
            self._stretch_s = resolved.duration
            self._stretch_at = time.monotonic()
        if with_popup:
            self._push_popup(with_popup)
        self.update()

    def play_click_feedback(self) -> None:
        """单击反馈：随机点头/左右摇摆（用户口径：单击只播动作，不加好感）。"""
        self.play_action(actions.random_click_action())

    def play_pat_feedback(self, event: object | None) -> None:
        """双击摸头反馈：播实例摸头动作池里随机的一个 + 好感飘字。

        :param event: :class:`world.events.PatEvent`；冷却中为 None（不播不飘字）。
        """
        if event is None:
            return
        tracker = self._world.mood_tracker(self._pet_cfg.id)
        delta = getattr(event, "delta", 0)
        action_key = getattr(event, "action_key", actions.PAT_ACTIONS[0])
        sign = f"+{delta:g}" if delta > 0 else f"{delta:g}"
        self.play_action(action_key, with_popup=f"摸摸头 {sign} → {tracker.value:.0f}")

    def play_mood_event(self, event: object) -> None:
        """拖拽/飞行结束时结算一条累计好感飘字（如「提起 +3 → 21」）。"""
        text = getattr(event, "text", None)
        if callable(text):
            self._push_popup(text())
        self.update()

    def play_music_reaction(self) -> None:
        """听见音乐时的回应：从实例设置的动作池里随机挑一个播放 + ♪ 飘字。"""
        pool = self._world.audio_for(self._pet_cfg.id).music_pool
        spec = actions.random_pool_action(pool, actions.MUSIC_ACTIONS)
        self.play_action(spec, with_popup=random.choice(C.MUSIC_TEXTS))

    def music_tick(self, music_mode: bool) -> None:
        """每帧音乐驱动：进入音乐模式后按实例间隔摇摆。

        :param music_mode: 是否已进入音乐模式（持续播放够久，见 audio.MusicGate）。
        """
        audio = self._world.audio_for(self._pet_cfg.id)
        if not audio.enabled:
            self._sway.reset()
            return
        self._sway.set_interval(audio.interval_seconds)
        now = time.monotonic()
        if self._sway.should_fire(music_mode and not self._state().dragging, now):
            self.play_music_reaction()

    # ---- 每帧推进 ----

    def tick(self) -> None:
        """每帧调用：动画推进 + 贴图/位置同步 + 飘字清理。"""
        now = time.monotonic()
        self._tick_flip(now)
        if self._stretch_at is not None and now - self._stretch_at >= self._stretch_s:
            self._stretch_at = None
        self.refresh_image()
        self.sync_geometry()
        if self._popups:
            alive = [(text, at) for text, at in self._popups if now - at < C.POPUP_S]
            if len(alive) != len(self._popups):
                self._popups = alive
                # 关键：飘字清空的同一帧必须重绘一次，否则最后一帧淡影会一直留在屏幕上
                self.update()
        if self._stretch_at is not None or self._flip_at is not None or self._popups:
            self.update()

    def _tick_flip(self, now: float) -> None:
        """翻转状态机：越中线自动翻转，动作触发的翻转按剩余次数连续播放。"""
        desired = self._desired_mirror()
        if desired != self._auto_mirror:
            self._auto_mirror = desired
            if self._flip_at is None and desired != self._mirrored:
                self._start_flip_run(1)
        if self._flip_at is None:
            return
        elapsed = now - self._flip_at
        if not self._flip_swapped and elapsed >= C.FLIP_HALF_S:
            self._mirrored = self._flip_to
            self._flip_swapped = True
        if elapsed >= C.FLIP_HALF_S * 2:
            self._flip_at = None
            if self._flip_left > 0:  # 左右摇摆：成对往返，偶数次必回原位
                self._start_flip_run(self._flip_left)

    def _start_flip_run(self, flips: int) -> None:
        """开始一轮翻转（flips 次），左右摇摆用 2 次保证回到原位。"""
        if self._flip_at is not None:
            self._flip_left = max(self._flip_left, flips)
            return
        self._flip_left = max(0, flips - 1)
        self._flip_at = time.monotonic()
        self._flip_from = self._mirrored
        self._flip_to = not self._mirrored
        self._flip_swapped = False

    def _stretch_scales(self) -> tuple[float, float]:
        """拉伸/压扁动作的 (sx, sy)。

        - stretch（点头）：先横拉回弹，再纵拉回弹；
        - squish（摸头）：整体纵向压扁 + 横向微鼓后回弹（绘制原点锚定脚底，
          见 rendering.paintEvent，视觉上像被按了一下头）。
        """
        if self._stretch_at is None:
            return 1.0, 1.0
        t = max(0.0, min(1.0, (time.monotonic() - self._stretch_at) / self._stretch_s))
        wave = 1.0 - abs(t * 2.0 - 1.0)  # 0→1→0
        if self._stretch_kind == "squish":
            return 1.0 + 0.14 * wave, 1.0 - 0.32 * wave
        amount = (C.CLICK_STRETCH - 1.0) * wave
        if t < 0.5:
            return 1.0 + amount, 1.0
        return 1.0, 1.0 + amount

    def _scales(self) -> tuple[float, float]:
        """当前 (scale_x, scale_y)：拉伸动作 + 翻转压扁的合成。"""
        sx, sy = self._stretch_scales()
        if self._flip_at is not None:
            ft = (time.monotonic() - self._flip_at) / C.FLIP_HALF_S  # 0..2
            sx *= abs(1.0 - ft)  # 1→0→1
        return sx, sy
