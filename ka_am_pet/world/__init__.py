"""ka_am_pet.world 包：多宠物统一物理世界。

对外接口保持与重构前的 ``ka_am_pet/world.py`` 完全一致::

    from ka_am_pet.world import PetWorld

内部按职责拆分：``core`` 主类、``runtime`` 拖拽会话/生效设置、``placement`` 落位纯函数。
"""

from .core import PetWorld
from .runtime import DragData, PetRuntimeSettings

__all__ = ["PetWorld", "PetRuntimeSettings", "DragData"]
