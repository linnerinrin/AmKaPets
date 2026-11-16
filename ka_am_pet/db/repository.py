"""InstanceDB：实例库的 CRUD 门面（纯 Python，禁 Qt）。

只负责「把 PetInstance 写进 / 读出 SQLite」；打开与降级逻辑在
connection.py，表结构与旧库迁移在 schema.py，数据模型在 models.py。
线程安全按调用方保证（UI 主线程使用）。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from ka_am_pet.db.connection import clear_readonly, open_database
from ka_am_pet.db.models import PetInstance, dump_overrides, load_overrides
from ka_am_pet.db.schema import _SELECT
from ka_am_pet.models import PetOverrides


class InstanceDB:
    """实例库：SQLite 单文件，线程按调用方保证（UI 主线程使用）。"""

    def __init__(self, path: Path) -> None:
        """打开（必要时创建）实例库并确保表结构存在。

        原库不可写（沙箱 / 只读盘 / 被其它实例独占）时，自动复制到可写目录
        继续使用，原因记录在 :attr:`recovered_note`，避免启动直接崩溃。

        :param path: SQLite 文件路径（父目录必须已存在）。
        """
        self._path = Path(path)
        self._conn, self._path, self._recovered = open_database(
            self._path, clear_readonly_fn=self._clear_readonly
        )

    # 保留为类上静态方法：既便于测试按类替换修复策略，也保持原私有接口形状。
    _clear_readonly = staticmethod(clear_readonly)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def recovered_note(self) -> str:
        """降级到应急库时的中文说明；正常情况为空串。"""
        return self._recovered

    def close(self) -> None:
        self._conn.close()

    # ---- CRUD ----

    def list_all(self) -> list[PetInstance]:
        """按创建时间升序列出全部实例。"""
        rows = self._conn.execute(f"{_SELECT} ORDER BY created_ts ASC").fetchall()
        return [self._row_to_instance(r) for r in rows]

    def get(self, instance_id: str) -> PetInstance | None:
        row = self._conn.execute(f"{_SELECT} WHERE id = ?", (instance_id,)).fetchone()
        return self._row_to_instance(row) if row else None

    def create(
        self,
        base: str,
        name: str,
        system_prompt: str = "",
        size: int = 320,
        x: float | None = None,
        y: float | None = None,
        overrides: PetOverrides | None = None,
        passthrough: bool = False,
    ) -> PetInstance:
        """新建实例；id 自动生成为 <base>-<序号>（唯一）。"""
        instance_id = self._unique_id(base)
        ts = time.time()
        overrides = overrides or PetOverrides()
        self._conn.execute(
            "INSERT INTO instances"
            " (id, base, name, system_prompt, size, x, y, created_ts, overrides_json, passthrough)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                instance_id,
                base,
                name,
                system_prompt,
                int(size),
                x,
                y,
                ts,
                dump_overrides(overrides),
                1 if passthrough else 0,
            ),
        )
        self._conn.commit()
        return PetInstance(
            id=instance_id,
            base=base,
            name=name,
            system_prompt=system_prompt,
            size=int(size),
            x=x,
            y=y,
            created_ts=ts,
            overrides=overrides,
            passthrough=passthrough,
        )

    def update(self, instance: PetInstance) -> None:
        """按 id 全字段更新（含覆盖组与覆盖模式）；id 不存在时静默忽略。"""
        self._conn.execute(
            "UPDATE instances SET base=?, name=?, system_prompt=?, size=?, x=?, y=?,"
            " overrides_json=?, passthrough=? WHERE id=?",
            (
                instance.base,
                instance.name,
                instance.system_prompt,
                int(instance.size),
                instance.x,
                instance.y,
                dump_overrides(instance.overrides),
                1 if instance.passthrough else 0,
                instance.id,
            ),
        )
        self._conn.commit()

    def update_position(self, instance_id: str, x: float, y: float) -> None:
        """只更新最后位置（退出时持久化用）。"""
        self._conn.execute(
            "UPDATE instances SET x=?, y=? WHERE id=?", (x, y, instance_id)
        )
        self._conn.commit()

    def set_passthrough(self, instance_id: str, passthrough: bool) -> None:
        """只更新覆盖模式开关。"""
        self._conn.execute(
            "UPDATE instances SET passthrough=? WHERE id=?",
            (1 if passthrough else 0, instance_id),
        )
        self._conn.commit()

    def delete(self, instance_id: str) -> None:
        """删除实例；不存在时静默忽略。"""
        self._conn.execute("DELETE FROM instances WHERE id=?", (instance_id,))
        self._conn.commit()

    # ---- 内部 ----

    def _unique_id(self, base: str) -> str:
        # 用 meta 表里的单调序号，保证删除后 id 不复用
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (f"seq_{base}",)
        ).fetchone()
        n = int(row[0]) + 1 if row else 1
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (f"seq_{base}", n),
        )
        return f"{base}-{n}"

    @staticmethod
    def _row_to_instance(row: sqlite3.Row) -> PetInstance:
        keys = row.keys()
        overrides = load_overrides(row["overrides_json"] if "overrides_json" in keys else "")
        return PetInstance(
            id=row["id"],
            base=row["base"],
            name=row["name"],
            system_prompt=row["system_prompt"] or "",
            size=int(row["size"]),
            x=row["x"],
            y=row["y"],
            created_ts=row["created_ts"],
            overrides=overrides,
            passthrough=bool(row["passthrough"]) if "passthrough" in keys else False,
        )
