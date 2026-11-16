"""桌宠「查看状态」互动的三个小件：状态面板、底部输入条、对话气泡。

布局规则（用户口径）：
- 单击桌宠 = 查看状态：桌宠上方贴一个 150~200px 宽的小状态面板（圆角 45、无标题栏），
  桌宠底部（不超过桌宠底端）贴一个输入条；点面板/桌宠以外的任何地方、双击、拖拽、
  甩抛飞行、发送消息，都会退出查看状态；
- 桌宠说完话后在上方单独显示对话气泡（底色=主题色1），点一下气泡就消失；
- overlay 模式没有这套互动（宠物只读展示，只剩眼睛按钮）。

本包按职责拆分：
- widgets.py：三个纯展示控件（StatusPanel / ChatInputBar / SpeechBubble）；
- controller.py：StatusView 控制器，管三件套的显隐、跟位与退出判定。
"""

from .controller import StatusView
from .widgets import ChatInputBar, SpeechBubble, StatusPanel

__all__ = ["ChatInputBar", "SpeechBubble", "StatusPanel", "StatusView"]
