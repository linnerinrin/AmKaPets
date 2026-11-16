"""应用装配包：对外接口与原 ``ka_am_pet.app`` 模块完全一致。

原单文件 ``app.py``（683 行）按职责拆为：

- ``core``      启动流程、主循环 tick、屏幕边界、优雅退出
- ``shell``     overlay/desktop 渲染壳的创建/切换/重建与贴图加载
- ``audio``     音乐律动（系统音频监听）的按需启停
- ``tray``      托盘图标与托盘/宠物右键菜单
- ``status``    查看状态面板与输入条简易对话
- ``chat``      对话窗口的创建/复用与按实例合并对话设置
- ``instances`` 实例新增/编辑/移除与覆盖模式同步
- ``settings``  全局设置对话框与保存后应用

各 mixin 通过组合在 :class:`PetApplication` 上，公共名不变。
"""

from __future__ import annotations

from .audio import AudioMixin
from .chat import ChatMixin
from .core import AppCore, _ReplyBridge
from .instances import InstancesMixin
from .settings import SettingsMixin
from .shell import ShellMixin
from .status import StatusMixin
from .tray import TrayMixin


class PetApplication(
    ShellMixin,
    AudioMixin,
    TrayMixin,
    StatusMixin,
    ChatMixin,
    InstancesMixin,
    SettingsMixin,
    AppCore,
):
    """应用主装配：配置/实例库/记忆/对话服务/渲染壳/托盘的创建与协调。"""


__all__ = ["PetApplication", "_ReplyBridge"]
