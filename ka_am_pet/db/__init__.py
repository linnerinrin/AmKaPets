"""宠物实例库：SQLite 长期存储（纯 Python，禁 Qt）。

实例 = 一只可命名的桌宠：基底角色（ame/kangel，决定贴图目录）+ 名字 +
独立 system_prompt + 尺寸 + 最后位置 + 覆盖设置组 + 覆盖模式开关。
会话记忆按实例 id 隔离（memory.py 本就以 pet_id 分组，天然隔离）。

本包按职责拆分（AGENTS.md 第 13 节）：

- ``models``：PetInstance 数据类与 overrides_json 序列化；
- ``schema``：建表 SQL、旧库补列与旧表迁移；
- ``connection``：打开 / 只读修复 / 降级到应急副本；
- ``repository``：InstanceDB 的 CRUD。

旧版 ``ka_am_pet.db`` 模块的全部公共名称在此 re-export，
既有 ``from ka_am_pet.db import X`` 调用不受影响。
"""

from ka_am_pet.db.connection import DatabaseReadOnly
from ka_am_pet.db.models import PetInstance
from ka_am_pet.db.repository import InstanceDB
from ka_am_pet.db.schema import SCHEMA

__all__ = ["DatabaseReadOnly", "InstanceDB", "PetInstance", "SCHEMA"]
