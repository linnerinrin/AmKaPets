"""单宠物渲染/命中/拖拽控件包（overlay 与 desktop 两种模式共用）。

历史原因：原 ``ka_am_pet/ui/pet_widget.py`` 超过 300 行硬上限，按 AGENTS.md
第 13 节拆分为职责单一的子模块，本 ``__init__`` 统一 re-export 公共名称，
保证 ``from ka_am_pet.ui.pet_widget import PetWidget`` 调用不破。

子模块职责：
- :mod:`.constants`：包内共享常量（阈值/时长/Win32 消息号）；
- :mod:`.animation`：动作（点头/摇摆/摸头）状态机、镜像翻转、心情飘字；
- :mod:`.rendering`：按心情贴图绘制（缩放缓存）、飘字与眼睛按钮的绘制；
- :mod:`.interaction`：鼠标交互转交 PetWorld、WM_NCHITTEST 按区域穿透；
- :mod:`.widget`：``PetWidget`` 组装各 mixin，负责构造、同步与生命周期。
"""

from ka_am_pet.ui.pet_widget.widget import PetWidget

__all__ = ["PetWidget"]
