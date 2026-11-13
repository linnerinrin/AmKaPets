"""InstanceDB：SQLite 实例库 CRUD 测试。"""

from __future__ import annotations

from ka_am_pet.db import InstanceDB


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
