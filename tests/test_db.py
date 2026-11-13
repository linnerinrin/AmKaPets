"""InstanceDB：SQLite 实例库 CRUD 测试。"""

from __future__ import annotations

from ka_am_pet.db import InstanceDB
from ka_am_pet.models import ChatOverrides, ChatSettings, effective_chat


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

    def test_instance_chat_overrides_roundtrip(self, tmp_path):
        """实例级对话覆盖项：新建 → 读回 → 更新 → 重开仍在。"""
        db = _db(tmp_path)
        ov = ChatOverrides(
            base_url="https://api.example.com/v1",
            api_key="sk-instance",
            model="gpt-4o",
            memory_rounds=3,
            timeout_seconds=20,
        )
        pid = db.create("kangel", "小天", chat=ov).id
        got = db.get(pid)
        assert got is not None
        assert (got.chat.base_url, got.chat.api_key, got.chat.model) == (
            "https://api.example.com/v1",
            "sk-instance",
            "gpt-4o",
        )
        assert (got.chat.memory_rounds, got.chat.timeout_seconds) == (3, 20)
        # 默认实例没有覆盖项 → 所有字段为空（等于继承全局）
        other = db.create("ame", "糖糖")
        assert other.chat.is_empty()
        # 更新覆盖项
        got.chat = ChatOverrides(model="gpt-4o-mini")
        db.update(got)
        assert db.get(pid).chat.model == "gpt-4o-mini"
        db.close()
        db2 = InstanceDB(tmp_path / "pets.db")
        assert db2.get(pid).chat.model == "gpt-4o-mini"
        db2.close()

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
