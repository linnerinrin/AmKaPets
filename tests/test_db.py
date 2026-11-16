"""InstanceDB：SQLite 实例库 CRUD 测试。"""

from __future__ import annotations

import os
import sqlite3
import stat

from ka_am_pet.db import InstanceDB
from ka_am_pet.models import (
    AudioSettings,
    ChatOverrides,
    ChatSettings,
    MoodSettings,
    PetOverrides,
    effective_chat,
)


def _db(tmp_path) -> InstanceDB:
    return InstanceDB(tmp_path / "pets.db")


class TestInstanceDB:
    def test_create_and_list(self, tmp_path):
        db = _db(tmp_path)
        id1 = db.create("kangel", "小天").id
        id2 = db.create("kangel", "小超").id
        id3 = db.create("ame", "糖糖").id
        assert id1 == "kangel-1"
        assert id2 == "kangel-2"
        assert id3 == "ame-1"
        rows = db.list_all()
        assert [r.id for r in rows] == ["kangel-1", "kangel-2", "ame-1"]
        assert rows[0].name == "小天"
        assert rows[2].size == 320
        db.close()

    def test_get_and_update(self, tmp_path):
        db = _db(tmp_path)
        pid = db.create("ame", "糖糖", system_prompt="你好").id
        inst = db.get(pid)
        assert inst is not None
        assert inst.system_prompt == "你好"
        inst.name = "糖糖二号"
        inst.size = 400
        db.update(inst)
        again = db.get(pid)
        assert again is not None
        assert again.name == "糖糖二号"
        assert again.size == 400
        db.close()

    def test_update_position(self, tmp_path):
        db = _db(tmp_path)
        pid = db.create("kangel", "小天").id
        db.update_position(pid, 100.0, 200.0)
        inst = db.get(pid)
        assert inst is not None
        assert (inst.x, inst.y) == (100.0, 200.0)
        db.close()

    def test_delete(self, tmp_path):
        db = _db(tmp_path)
        pid = db.create("ame", "糖糖").id
        db.delete(pid)
        assert db.get(pid) is None
        assert db.list_all() == []
        db.close()

    def test_id_no_reuse_after_delete(self, tmp_path):
        db = _db(tmp_path)
        id1 = db.create("kangel", "A").id
        db.delete(id1)
        id2 = db.create("kangel", "B").id
        assert id2 != id1
        db.close()

    def test_persist_across_open(self, tmp_path):
        db = _db(tmp_path)
        pid = db.create("ame", "糖糖").id
        db.close()
        db2 = InstanceDB(tmp_path / "pets.db")
        inst = db2.get(pid)
        assert inst is not None
        assert inst.name == "糖糖"
        db2.close()

    def test_instance_overrides_roundtrip(self, tmp_path):
        """实例设置组：新建 → 读回 → 更新 → 重开仍在（第四轮起是完整设置）。"""
        db = _db(tmp_path)
        chat = ChatSettings(
            base_url="https://api.example.com/v1",
            api_key="sk-instance",
            model="gpt-4o",
            system_prompt="我是小天",
            memory_rounds=3,
            timeout_seconds=20,
        )
        pid = db.create("kangel", "小天", overrides=PetOverrides(chat=chat)).id
        got = db.get(pid)
        assert got is not None
        assert (
            got.overrides.chat.base_url,
            got.overrides.chat.api_key,
            got.overrides.chat.model,
        ) == ("https://api.example.com/v1", "sk-instance", "gpt-4o")
        assert (got.overrides.chat.memory_rounds, got.overrides.chat.timeout_seconds) == (3, 20)
        # 默认实例拿的是出厂设置组（不再有「空组=跟随全局」）
        other = db.create("ame", "糖糖")
        assert other.overrides.chat.model == ChatSettings().model
        assert other.overrides.pat_pool == PetOverrides().pat_pool
        # 更新：换整组（旧对话设置被整组替换）
        got.overrides = PetOverrides(
            chat=ChatSettings(model="gpt-4o-mini"),
            music=AudioSettings(music_pool=("sway",), interval_seconds=2.5),
            pat_pool=("nod", "sway"),
        )
        db.update(got)
        again = db.get(pid)
        assert again.overrides.chat.model == "gpt-4o-mini"
        assert again.overrides.music.music_pool == ("sway",)
        assert again.overrides.music.interval_seconds == 2.5
        assert again.overrides.pat_pool == ("nod", "sway")
        db.close()
        db2 = InstanceDB(tmp_path / "pets.db")
        reopened = db2.get(pid)
        assert reopened.overrides.chat.model == "gpt-4o-mini"
        assert reopened.overrides.pat_pool == ("nod", "sway")
        db2.close()

    def test_passthrough_flag_roundtrip(self, tmp_path):
        """覆盖模式（点不到）标记持久化。"""
        db = _db(tmp_path)
        pid = db.create("kangel", "小天").id
        assert db.get(pid).passthrough is False
        db.set_passthrough(pid, True)
        assert db.get(pid).passthrough is True
        db.close()
        db2 = InstanceDB(tmp_path / "pets.db")
        assert db2.get(pid).passthrough is True
        db2.close()

    def test_mood_numbers_are_not_persisted(self, tmp_path):
        """第四轮起好感数值写死：实例设置组里不再有 mood 组，数据库里也不存。"""
        db = _db(tmp_path)
        pid = db.create("ame", "糖糖", overrides=PetOverrides(pat_pool=("pat",))).id
        got = db.get(pid).overrides
        assert not hasattr(got, "mood")
        assert got.pat_pool == ("pat",)
        db.close()

    def test_effective_chat_merges_instance_overrides(self):
        """effective_chat：实例覆盖优先，未覆盖项回退全局，提示词按需拼接。"""
        glob = ChatSettings(
            base_url="https://global.example/v1",
            api_key="sk-global",
            model="global-model",
            system_prompt="全局人格",
            memory_rounds=5,
            timeout_seconds=45,
        )
        # 全空覆盖 → 完全继承
        same = effective_chat(glob, ChatOverrides())
        assert (same.base_url, same.api_key, same.model) == (
            "https://global.example/v1",
            "sk-global",
            "global-model",
        )
        assert same.memory_rounds == 5 and same.timeout_seconds == 45
        # 部分覆盖 + 实例人格 + 心情提示词
        merged = effective_chat(
            glob, ChatOverrides(model="own-model", memory_rounds=2), "我是小天", "心情很好"
        )
        assert merged.model == "own-model"
        assert merged.memory_rounds == 2
        assert merged.api_key == "sk-global"  # 未覆盖 → 全局
        assert merged.system_prompt == "我是小天\n心情很好"
        # 入参不被修改
        assert glob.system_prompt == "全局人格"


def _legacy_db(tmp_path):
    """造一个旧版库：缺 overrides_json/passthrough，启动时必须 ALTER。"""
    db_path = tmp_path / "pets.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE instances ("
        " id TEXT PRIMARY KEY, base TEXT NOT NULL, name TEXT NOT NULL,"
        " system_prompt TEXT NOT NULL DEFAULT '', size INTEGER NOT NULL DEFAULT 320,"
        " x REAL, y REAL, created_ts REAL NOT NULL);"
        "INSERT INTO instances (id, base, name, created_ts)"
        " VALUES ('kangel-1', 'kangel', '旧记录', 1.0);"
    )
    conn.commit()
    conn.close()
    return db_path


class TestReadOnlyRecovery:
    """只读库：先原地修「只读属性」，修不动再复制到可写目录（不崩、不丢数据）。"""

    def test_readonly_attr_is_repaired_in_place(self, tmp_path):
        db_path = _legacy_db(tmp_path)
        os.chmod(db_path, stat.S_IREAD)
        try:
            db = InstanceDB(db_path)
            # 原地修复：不搬家、不提示
            assert db.recovered_note == ""
            assert db.path == db_path
            assert [row.name for row in db.list_all()] == ["旧记录"]
            assert db.create("ame", "新记录").id == "ame-1"
            db.close()
        finally:
            os.chmod(db_path, stat.S_IWRITE)

    def test_readonly_db_is_recovered_to_writable_dir(self, tmp_path, monkeypatch):
        db_path = _legacy_db(tmp_path)
        monkeypatch.setattr(InstanceDB, "_clear_readonly", staticmethod(lambda path: False))
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
        os.chmod(db_path, stat.S_IREAD)
        try:
            db = InstanceDB(db_path)
            assert db.recovered_note
            assert [row.name for row in db.list_all()] == ["旧记录"]
            assert db.create("ame", "新记录").id == "ame-1"
            assert db.get("kangel-1").overrides.chat.model == ChatSettings().model
            db.close()
            # 应急库在可写目录里，原库保持不动
            assert db.path == tmp_path / "local" / "ka-am-pet" / "pets.db"
            assert db.path.exists()
        finally:
            os.chmod(db_path, stat.S_IWRITE)
