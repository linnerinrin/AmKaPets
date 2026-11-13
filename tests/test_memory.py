"""对话记忆测试。"""

import json

from ka_am_pet.services.memory import MemoryStore


def test_full_history_persisted(tmp_path):
    """用户消息与成功回复全量追加保存，不自动删除。"""
    path = tmp_path / "memory.json"
    store = MemoryStore(path, memory_rounds=2)
    for i in range(6):
        store.append("kangel", "user", f"问{i}")
        store.append("kangel", "assistant", f"答{i}")
    # 重新加载后全量仍在
    store2 = MemoryStore(path, memory_rounds=2)
    assert len(store2.all_messages("kangel")) == 12


def test_context_truncated_to_memory_rounds(tmp_path):
    """context_for 只返回最近 memory_rounds 轮（一轮 = user + assistant）。"""
    path = tmp_path / "memory.json"
    store = MemoryStore(path, memory_rounds=2)
    for i in range(5):
        store.append("ame", "user", f"问{i}")
        store.append("ame", "assistant", f"答{i}")
    ctx = store.context_for("ame")
    assert len(ctx) == 4  # 2 轮 = 4 条
    assert ctx[0]["content"] == "问3"
    assert ctx[-1] == {"role": "assistant", "content": "答4"}


def test_corrupt_json_backed_up_and_reset(tmp_path):
    """损坏 JSON 备份为 memory.corrupt-<ts>.json 后重新开始，不崩溃。"""
    path = tmp_path / "memory.json"
    path.write_text("!!损坏!!", encoding="utf-8")
    store = MemoryStore(path, memory_rounds=5)
    assert store.all_messages("kangel") == []
    assert list(tmp_path.glob("memory.corrupt-*.json"))
    store.append("kangel", "user", "新对话")
    assert len(store.all_messages("kangel")) == 1


def test_pets_isolated_and_invalid_role_rejected(tmp_path):
    """不同宠物记忆互相隔离；非法 role 拒绝写入。"""
    path = tmp_path / "memory.json"
    store = MemoryStore(path, memory_rounds=5)
    store.append("kangel", "user", "给超天酱")
    store.append("ame", "user", "给糖糖")
    assert len(store.all_messages("kangel")) == 1
    assert store.all_messages("ame")[0].content == "给糖糖"
    try:
        store.append("ame", "system", "不许写")
    except ValueError:
        pass
    else:
        raise AssertionError("非法 role 应抛 ValueError")
    assert len(store.all_messages("ame")) == 1
