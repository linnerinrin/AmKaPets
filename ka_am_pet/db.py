"""宠物实例库：SQLite 长期存储（纯 Python，禁 Qt）。

实例 = 一只可命名的桌宠：基底角色（ame/kangel，决定贴图目录）+ 名字 +
独立 system_prompt + 尺寸 + 最后位置。会话记忆按实例 id 隔离（memory.py
本就以 pet_id 分组，天然隔离）。
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from ka_am_pet.models import ChatOverrides

SCHEMA = """
CREATE TABLE IF NOT EXISTS instances (
    id TEXT PRIMARY KEY,
    base TEXT NOT NULL,
    name TEXT NOT NULL,
    system_prompt TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 320,
    x REAL,
    y REAL,
    created_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS instance_chat (
    id TEXT PRIMARY KEY,
    base_url TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    memory_rounds INTEGER NOT NULL DEFAULT 0,
    timeout_seconds INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
"""

# 实例 + 覆盖项的联合查询列（instance_chat 缺行时全为 NULL，回退成空覆盖）
_SELECT = (
    "SELECT i.*, c.base_url AS c_base_url, c.api_key AS c_api_key, c.model AS c_model,"
    " c.memory_rounds AS c_memory_rounds, c.timeout_seconds AS c_timeout_seconds"
    " FROM instances i LEFT JOIN instance_chat c ON c.id = i.id"
)


@dataclass
class PetInstance:
    """一只桌宠实例（数据库行）。"""

    id: str
    base: str            # 基底角色 id（assets/pets/<base>/ 贴图目录）
    name: str            # 用户起的名字
    system_prompt: str = ""
    size: int = 320
    x: float | None = None
    y: float | None = None
    created_ts: float = 0.0
    chat: ChatOverrides = field(default_factory=ChatOverrides)  # 实例级 API 覆盖


class InstanceDB:
    """实例库：SQLite 单文件，线程按调用方保证（UI 主线程使用）。"""

    def __init__(self, path: Path) -> None:
        """打开（必要时创建）实例库并确保表结构存在。

        :param path: SQLite 文件路径（父目录必须已存在）。
        """
        self._path = Path(path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._conn.close()

    # ---- CRUD ----

    def list_all(self) -> list[PetInstance]:
        """按创建时间升序列出全部实例（含实例级对话覆盖项）。"""
        rows = self._conn.execute(f"{_SELECT} ORDER BY i.created_ts ASC").fetchall()
        return [self._row_to_instance(r) for r in rows]

    def get(self, instance_id: str) -> PetInstance | None:
        row = self._conn.execute(f"{_SELECT} WHERE i.id = ?", (instance_id,)).fetchone()
        return self._row_to_instance(row) if row else None

    def create(
        self,
        base: str,
        name: str,
        system_prompt: str = "",
        size: int = 320,
        x: float | None = None,
        y: float | None = None,
        chat: ChatOverrides | None = None,
    ) -> PetInstance:
        """新建实例；id 自动生成为 <base>-<序号>（唯一）。"""
        instance_id = self._unique_id(base)
        ts = time.time()
        self._conn.execute(
            "INSERT INTO instances (id, base, name, system_prompt, size, x, y, created_ts)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (instance_id, base, name, system_prompt, int(size), x, y, ts),
        )
        self._save_chat(instance_id, chat or ChatOverrides())
        self._conn.commit()
        return PetInstance(
            instance_id, base, name, system_prompt, int(size), x, y, ts, chat or ChatOverrides()
        )

    def update(self, instance: PetInstance) -> None:
        """按 id 全字段更新（含实例级对话覆盖项）；id 不存在时静默忽略。"""
        self._conn.execute(
            "UPDATE instances SET base=?, name=?, system_prompt=?, size=?, x=?, y=? WHERE id=?",
            (
                instance.base,
                instance.name,
                instance.system_prompt,
                int(instance.size),
                instance.x,
                instance.y,
                instance.id,
            ),
        )
        self._save_chat(instance.id, instance.chat)
        self._conn.commit()

    def update_position(self, instance_id: str, x: float, y: float) -> None:
        """只更新最后位置（退出时持久化用）。"""
        self._conn.execute(
            "UPDATE instances SET x=?, y=? WHERE id=?", (x, y, instance_id)
        )
        self._conn.commit()

    def delete(self, instance_id: str) -> None:
        """删除实例及其对话覆盖项；不存在时静默忽略。"""
        self._conn.execute("DELETE FROM instances WHERE id=?", (instance_id,))
        self._conn.execute("DELETE FROM instance_chat WHERE id=?", (instance_id,))
        self._conn.commit()

    # ---- 内部 ----

    def _save_chat(self, instance_id: str, chat: ChatOverrides) -> None:
        """整行覆盖写实例级对话设置（不存在则插入）。"""
        self._conn.execute(
            "INSERT INTO instance_chat"
            " (id, base_url, api_key, model, memory_rounds, timeout_seconds)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET base_url=excluded.base_url,"
            " api_key=excluded.api_key, model=excluded.model,"
            " memory_rounds=excluded.memory_rounds, timeout_seconds=excluded.timeout_seconds",
            (
                instance_id,
                chat.base_url,
                chat.api_key,
                chat.model,
                int(chat.memory_rounds),
                int(chat.timeout_seconds),
            ),
        )

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
        chat = ChatOverrides(
            base_url=(row["c_base_url"] or "") if "c_base_url" in keys else "",
            api_key=(row["c_api_key"] or "") if "c_api_key" in keys else "",
            model=(row["c_model"] or "") if "c_model" in keys else "",
            memory_rounds=int(row["c_memory_rounds"] or 0) if "c_memory_rounds" in keys else 0,
            timeout_seconds=int(row["c_timeout_seconds"] or 0) if "c_timeout_seconds" in keys else 0,
        )
        return PetInstance(
            id=row["id"],
            base=row["base"],
            name=row["name"],
            system_prompt=row["system_prompt"] or "",
            size=int(row["size"]),
            x=row["x"],
            y=row["y"],
            created_ts=row["created_ts"],
            chat=chat,
        )
