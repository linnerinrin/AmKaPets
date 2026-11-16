"""pet_widget 包共享常量：交互阈值、动画时长、眼睛按钮与 Win32 消息号。

集中定义避免魔法数字散落各 mixin；数值含义见各常量行内注释。
"""

CLICK_MAX_MOVE_PX = 6    # 点击与拖拽的位移阈值（px）
CLICK_MAX_MS = 400       # 单击最长按压时间（ms）
PAT_MAX_INTERVAL_MS = 500  # 双击摸头的两次点击最大间隔（ms）
# 说明：不用 QApplication.doubleClickInterval()——它跟随系统「鼠标双击速度」设置，
# 用户机器实测只有 400ms，手慢一点的双击会被误判成两次单击。固定 500ms 符合用户口径。

CLICK_STRETCH = 1.25     # 拉伸类动作的幅度
FLIP_HALF_S = 0.10       # 镜像翻转「压扁」或「展开」单侧时长（s）
POPUP_S = 0.9            # 心情浮动飘字时长（s）
POPUP_MAX = 5            # 同时最多几条飘字
MUSIC_TEXTS = ("♪", "♪ 好听", "♫ 摇摆", "♪ 一起听")

EYE_MIN = 22             # 眼睛按钮直径下限（px）
EYE_MAX = 34             # 眼睛按钮直径上限（px）
EYE_MARGIN = 6           # 眼睛按钮贴边距（px）

# Win32 原生命中测试（desktop 模式单窗口按区域穿透）
WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1
HTCLIENT = 1
