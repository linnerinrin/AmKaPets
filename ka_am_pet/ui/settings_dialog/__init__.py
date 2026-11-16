"""设置对话框包：左侧分页（信息 / 聊天 / 交互），右侧具体选项。

- :class:`SettingsDialog`：托盘里的「UI 设置」（运行模式 / 透明度 / 主题色）。
- :class:`InstanceSettingsDialog`：单实例设置，所有配置都按实例保存
  （第四轮起不再有「跟随全局」）。

界面约定（用户口径）：
- 不显示任何批注式小字（说明全靠占位符/ToolTip 或字段名本身）；
- 选项按内容定宽，不每个都独占一行（min/max 成对、短字段合并到同一行）；
- 主题色只在「UI 设置」里配（预设主题或自定义两个色）。

本模块仅 re-export 公共名称，保证 ``from ka_am_pet.ui.settings_dialog import X`` 不破。
"""

from .global_dialog import SettingsDialog
from .instance_dialog import InstanceSettingsDialog

__all__ = ["SettingsDialog", "InstanceSettingsDialog"]
