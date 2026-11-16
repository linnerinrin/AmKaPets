"""实例库表结构定义与旧库升级（建表 / 补列 / 迁移旧表）。

独立成模块的原因：SQL 文本与升级逻辑是「数据库长什么样」的知识，
和「怎么打开」「怎么读写」是两种职责（AGENTS.md 第 13.2 节 SRP）。
"""

from __future__ import annotations

import sqlite3

from ka_am_pet.db.models import dump_overrides, load_overrides
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
    created_ts REAL NOT NULL,
    overrides_json TEXT NOT NULL DEFAULT '',
    passthrough INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
"""

_SELECT = "SELECT * FROM instances"


def setup_schema(conn: sqlite3.Connection) -> None:
    """建表 + 补列 + 迁移旧表（同一连接）。"""
    conn.executescript(SCHEMA)
    conn.commit()
    ensure_columns(conn)
    migrate_legacy_chat(conn)


def ensure_columns(conn: sqlite3.Connection) -> None:
    """旧库升级：补齐 overrides_json / passthrough 列。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(instances)")}
    if "overrides_json" not in columns:
        conn.execute(
            "ALTER TABLE instances ADD COLUMN overrides_json TEXT NOT NULL DEFAULT ''"
        )
    if "passthrough" not in columns:
        conn.execute(
            "ALTER TABLE instances ADD COLUMN passthrough INTEGER NOT NULL DEFAULT 0"
        )
    conn.commit()


def migrate_legacy_chat(conn: sqlite3.Connection) -> None:
    """把旧 instance_chat 表的数据并进 overrides_json，然后删除旧表。"""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='instance_chat'"
    ).fetchone()
    if not exists:
        return
    rows = conn.execute("SELECT * FROM instance_chat").fetchall()
    for row in rows:
        chat = ChatOverrides(
            base_url=row["base_url"] or "",
            api_key=row["api_key"] or "",
            model=row["model"] or "",
            memory_rounds=int(row["memory_rounds"] or 0),
            timeout_seconds=int(row["timeout_seconds"] or 0),
        )
        if chat.is_empty():
            continue
        target = conn.execute(
            "SELECT overrides_json FROM instances WHERE id=?", (row["id"],)
        ).fetchone()
        if target is None:
            continue
        overrides = load_overrides(target["overrides_json"])
        if overrides.chat is None:
            overrides.chat = chat
            conn.execute(
                "UPDATE instances SET overrides_json=? WHERE id=?",
                (dump_overrides(overrides), row["id"]),
            )
    conn.execute("DROP TABLE instance_chat")
    conn.commit()
