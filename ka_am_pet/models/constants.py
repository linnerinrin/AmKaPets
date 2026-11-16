"""models 包共享常量：动作池与心情档位。

常量的含义见 AGENTS.md §6.5（心情四档）与 actions.py（动作表）。
集中定义避免各模块各自硬编码字符串。
"""

from ..actions import ACTIONS

# 音乐律动的候选动作 = 动作表全体（设置里用勾选列表自选，可多选；
# 所以这里直接由 actions.py 的动作表派生，新增动作自动进列表，无需改本文件）。
# actions.py 是纯规格表（无 Qt、无运行时状态），models 引用它不构成反向依赖。
MUSIC_POOL = tuple(ACTIONS)
ACTION_LABELS = {key: spec.label for key, spec in ACTIONS.items()}

#: 心情档位（从高到低），边界值归较高档。
MOOD_LEVELS = ("happy", "smile", "sad", "angry")
