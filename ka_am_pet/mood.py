"""心情系统：心情值、线性衰减、交互增益、四档映射与提示词/贴图联动（纯 Python，禁 Qt）。

规则（详见 AGENTS.md §6.5）：
- 心情值 0–100，初始 80，随时间线性下降（decay_per_second，默认 0.1/s）。
- 点击 +click_boost；拖拽中每秒 +drag_boost_per_second；甩抛成功 +throw_boost。
- 四档：[75,100]=happy，[50,74]=smile，[25,49]=sad，[0,24]=angry（含左端点）。
- 档位决定宠物贴图（{pet}-{mood}.png）与对话 system prompt 末尾的心情描述。
- 心情不持久化，每次启动回到 initial。
"""

from __future__ import annotations

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


class MoodTracker:
    """单只宠物的心情跟踪器：保存心情值并按真实时间差衰减、按交互增益。"""

    def __init__(self, settings: MoodSettings | None = None) -> None:
        """初始化心情跟踪器。

        :param settings: 心情设置；None 时使用默认值。心情值初始为 settings.initial。
        """
        self._settings = settings or MoodSettings()
        self._value = clamp_mood(self._settings.initial)
        self.last_delta: float = 0.0  # 最近一次 apply_delta 的实际增量（飘字显示用）

    @property
    def value(self) -> float:
        """当前心情值（已钳制在 [0, 100]）。"""
        return self._value

    @property
    def level(self) -> str:
        """当前档位名。"""
        return mood_level(self._value)

    def update(self, dt: float) -> str:
        """按真实时间差线性衰减心情值。

        :param dt: 距上次更新的真实时间（秒），调用方应已做上限钳制；负值按 0 处理。
        :return: 衰减后的档位名（便于调用方检测档位切换）。
        """
        self._value = clamp_mood(self._value - max(0.0, dt) * self._settings.decay_per_second)
        return self.level

    def apply_delta(self, delta: float) -> str:
        """直接施加一个心情增量（钳制到 0-100），并记录 last_delta。

        :param delta: 心情增量（可为负）。
        :return: 变化后的档位名。
        """
        self._value = clamp_mood(self._value + delta)
        self.last_delta = delta
        return self.level

    def on_click(self) -> str:
        """点击增益：+click_boost（钳制到上限）。

        :return: 增益后的档位名。
        """
        return self.apply_delta(self._settings.click_boost)

    def on_drag(self, dt: float) -> str:
        """拖拽增益：+drag_boost_per_second * dt（钳制到上限）。

        :param dt: 本次拖拽持续的时间（秒）。
        :return: 增益后的档位名。
        """
        self._value = clamp_mood(self._value + max(0.0, dt) * self._settings.drag_boost_per_second)
        return self.level

    def on_throw(self) -> str:
        """甩抛成功增益：+throw_boost（钳制到上限）。

        :return: 增益后的档位名。
        """
        self._value = clamp_mood(self._value + self._settings.throw_boost)
        return self.level

    def prompt(self) -> str:
        """当前档位的心情提示词（考虑配置覆盖）。"""
        return mood_prompt(self.level, self._settings)
