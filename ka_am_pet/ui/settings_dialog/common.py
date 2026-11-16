"""设置对话框共享常量与小工具。

集中定义输入框宽度、运行模式文案等常量，避免各分页模块重复魔法值。
"""

from __future__ import annotations

MODE_LABELS = {"desktop": "桌面模式", "overlay": "覆盖模式"}
CUSTOM_THEME = "custom"

#: 选项输入框统一的最大宽度（按内容定宽，不拉伸整行）
FIELD_MAX_W = 110
