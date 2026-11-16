"""心情系统：心情值、线性衰减、交互增益、四档映射与提示词/贴图联动（纯 Python，禁 Qt）。

规则（详见 AGENTS.md §6.5）：
- 心情值 0–100，初始 80，随时间线性下降（decay_per_second，默认 0.1/s）。
- 点击 +click_boost；拖拽中每秒 +drag_boost_per_second；甩抛成功 +throw_boost。
- 四档：[75,100]=happy，[50,74]=smile，[25,49]=sad，[0,24]=angry（含左端点）。
- 档位决定宠物贴图（{pet}-{mood}.png）与对话 system prompt 末尾的心情描述。
- 心情不持久化，每次启动回到 initial。
"""

from __future__ import annotations

import random
from collections.abc import Callable

from .models import MoodSettings

MOOD_MIN = 0.0
MOOD_MAX = 100.0

MOOD_LEVELS: tuple[str, ...] = ("happy", "smile", "sad", "angry")
"""全部档位名（高到低）。"""

DEFAULT_PROMPTS: dict[str, str] = {
    "happy": "你现在心情超好，回答活泼热情，可以撒个娇。",
    "smile": "你现在心情不错，回答温和友善。",
    "sad": "你现在有点难过，回答蔫蔫的、简短无力。",
    "angry": "你现在心情很差，说话带刺但不超过两句话。",
}
"""各档位默认心情提示词；可被配置 MoodSettings.prompts 覆盖。"""


def clamp_mood(value: float) -> float:
    """把心情值钳制到 [MOOD_MIN, MOOD_MAX]。

    :param value: 任意心情值。
    :return: 钳制后的心情值。
    """
    return min(max(value, MOOD_MIN), MOOD_MAX)


def mood_level(value: float) -> str:
    """心情值 → 档位名。区间 [75,100] [50,74] [25,49] [0,24]，含左端点。

    :param value: 心情值（调用前无需钳制，内部会处理）。
    :return: "happy" / "smile" / "sad" / "angry"。
    """
    v = clamp_mood(value)
    if v >= 75.0:
        return "happy"
    if v >= 50.0:
        return "smile"
    if v >= 25.0:
        return "sad"
    return "angry"


def mood_prompt(level: str, settings: MoodSettings | None = None) -> str:
    """档位 → 心情提示词（配置覆盖优先，缺省用 DEFAULT_PROMPTS）。

    :param level: 档位名。
    :param settings: 心情设置；prompts 中该档非空时优先使用。
    :return: 拼到 system prompt 末尾的一句心情描述；未知档位返回空串。
    """
    if level not in MOOD_LEVELS:
        return ""
    if settings is not None:
        override = settings.prompts.get(level, "")
        if override:
            return override
    return DEFAULT_PROMPTS[level]


def mood_image_name(pet_id: str, level: str) -> str:
    """档位 → 贴图文件名（{pet}-{mood}.png）。

    :param pet_id: 宠物 id（素材目录名，如 kangel / ame）。
    :param level: 档位名。
    :return: 文件名，如 "kangel-happy.png"。
    """
    return f"{pet_id}-{level}.png"


CLICKS_PER_BOOST = 2
"""每多少次单击才加一次好感（用户口径：每两次点击才会增加一次好感）。"""


class ClickCounter:
    """单击计数 + 冷却：只有「有效点击」才推进计数，攒满 every 次才给一次好感。

    冷却期间（动画还在播）的点击只播动作、不计数，避免狂点刷好感；冷却由调用方
    传入（本项目取所有动作的最长时长，见 actions.CLICK_COOLDOWN_SECONDS）。
    """

    def __init__(self, every: int = CLICKS_PER_BOOST, cooldown: float = 0.0) -> None:
        """初始化计数器。

        :param every: 攒满多少次点击算一次好感增益（至少 1）。
        :param cooldown: 每次增益后的冷却秒数，冷却内的点击不计数。
        """
        self.every = max(1, int(every))
        self.cooldown = max(0.0, float(cooldown))
        self._count = 0
        self._ready_at = 0.0

    @property
    def count(self) -> int:
        """当前已累积的有效点击数（0 .. every-1）。"""
        return self._count

    @property
    def remaining(self) -> int:
        """还差几次点击才加好感。"""
        return max(0, self.every - self._count)

    def cooldown_left(self, now: float) -> float:
        """距离下次计数解禁还剩多少秒（<=0 表示已解禁）。"""
        return max(0.0, self._ready_at - now)

    def register(self, now: float) -> bool:
        """登记一次点击。

        :param now: 当前时间（秒，单调时钟）。
        :return: True 表示这次点击攒满并触发好感增益（同时进入冷却、计数清零）。
        """
        if now < self._ready_at:
            return False
        self._count += 1
        if self._count < self.every:
            return False
        self._count = 0
        self._ready_at = now + self.cooldown
        return True



class MoodTracker:
    """单只宠物的心情跟踪器：保存心情值并按真实时间差衰减、按交互增益。

    增益是「整数随机区间」：摸头/点击在 [pat_min, pat_max] 里每次 randint，
    拖拽与飞行每秒各自在对应区间 randint 一次（不足 1 秒的时间会累积）。
    """

    def __init__(self, settings: MoodSettings | None = None, rng: Callable[[int, int], int] | None = None) -> None:
        """初始化心情跟踪器。

        :param settings: 心情设置；None 时使用默认值。心情值初始为 settings.initial。
        :param rng: 区间随机函数 (lo, hi) -> int，默认 random.randint（测试可注入固定值）。
        """
        self._settings = settings or MoodSettings()
        self._rng = rng or random.randint
        self._value = clamp_mood(self._settings.initial)
        self._drag_acc = 0.0    # 拖拽时间累计（秒），满 1 秒掷一次区间
        self._flight_acc = 0.0  # 飞行时间累计（秒）
        self._practice = False  # 直播练习：值钉在 100、不衰减、不增益
        self._practice_saved = 0.0  # 进入直播练习前的值，退出时恢复
        self.last_delta: float = 0.0  # 最近一次 apply_delta 的实际增量（飘字显示用）

    @property
    def value(self) -> float:
        """当前心情值（已钳制在 [0, 100]）。"""
        return self._value

    @property
    def practice(self) -> bool:
        """是否处于直播练习模式（好感冻结在 100）。"""
        return self._practice

    @property
    def level(self) -> str:
        """当前档位名。"""
        return mood_level(self._value)

    def set_practice(self, on: bool) -> None:
        """进入/退出直播练习模式。

        进入时先记下当前值再钉到 100，期间 :meth:`update` 不衰减、
        :meth:`apply_delta` 与各区间增益一律无效；退出时恢复进入前的值
        （用户口径：取消后直接回原来状态）。

        :param on: True 进入，False 退出。
        """
        if on and not self._practice:
            self._practice_saved = self._value
            self._value = clamp_mood(100.0)
            self._practice = True
        elif not on and self._practice:
            self._value = clamp_mood(self._practice_saved)
            self._practice = False
        self.last_delta = 0.0

    def set_settings(self, settings: MoodSettings) -> None:
        """热更新心情设置（全局/实例设置保存后调用），当前心情值保持不变。

        :param settings: 新的心情设置。
        """
        self._settings = settings
        self._value = clamp_mood(self._value)

    def update(self, dt: float) -> str:
        """按真实时间差线性衰减心情值。

        :param dt: 距上次更新的真实时间（秒），调用方应已做上限钳制；负值按 0 处理。
        :return: 衰减后的档位名（便于调用方检测档位切换）。
        """
        if self._practice:
            return self.level
        self._value = clamp_mood(self._value - max(0.0, dt) * self._settings.decay_per_second)
        return self.level

    def apply_delta(self, delta: float) -> str:
        """直接施加一个心情增量（钳制到 0-100），并记录 last_delta。

        :param delta: 心情增量（可为负）。
        :return: 变化后的档位名。
        """
        if self._practice:
            self.last_delta = 0.0
            return self.level
        self._value = clamp_mood(self._value + delta)
        self.last_delta = delta
        return self.level

    def roll_pat(self) -> int:
        """摸头/点击增益：在 [pat_min, pat_max] 里随机一次并施加，返回实际增量。"""
        if self._practice:
            return 0
        delta = self._rng(self._settings.pat_min, self._settings.pat_max)
        self.apply_delta(delta)
        return delta

    def _roll_per_second(self, dt: float, acc: float, lo: int, hi: int) -> tuple[float, int]:
        """每秒区间随机的通用累积：返回 (新的累计秒数, 本次施加的总增量)。"""
        acc += max(0.0, dt)
        if self._practice:
            return acc, 0
        total = 0
        while acc >= 1.0:
            acc -= 1.0
            total += self._rng(lo, hi)
        if total:
            self.apply_delta(total)
        return acc, total

    def on_drag(self, dt: float) -> int:
        """拖拽增益：每满 1 秒在 [drag_min, drag_max] 里随机一次；返回本次增量（可为 0）。"""
        self._drag_acc, total = self._roll_per_second(dt, self._drag_acc, self._settings.drag_min, self._settings.drag_max)
        return total

    def on_flight(self, dt: float) -> int:
        """飞行增益：每满 1 秒在 [flight_min, flight_max] 里随机一次；返回本次增量（可为 0）。"""
        self._flight_acc, total = self._roll_per_second(dt, self._flight_acc, self._settings.flight_min, self._settings.flight_max)
        return total

    def prompt(self) -> str:
        """当前档位的心情提示词（考虑配置覆盖）。"""
        return mood_prompt(self.level, self._settings)
