"""全量 JSON 对话记忆存储：按宠物 id 分组、线程安全快照、损坏备份、原子写。

严禁 import Qt；本模块保持纯 Python 以便单测与在 worker 线程中使用。
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from ka_am_pet.models import ChatMessage


class MemoryStore:
    """按宠物 id 分组的全量对话记忆（JSON 文件持久化）。"""

    def __init__(self, path: Path, memory_rounds: int) -> None:
        """初始化记忆存储。

        :param path: 记忆 JSON 文件路径。
        :param memory_rounds: 发给模型的最近轮数（一轮 = user + assistant）。
        """
        self._path = Path(path)
        self._memory_rounds = max(1, int(memory_rounds))
        self._lock = threading.Lock()
        self._messages: dict[str, list[ChatMessage]] = {}
        self._load()

    def append(self, pet_id: str, role: str, content: str) -> None:
        """追加一条消息（用户消息与成功的助手回复全量追加，失败回复不写入）。

        :param pet_id: 宠物 id。
        :param role: "user" 或 "assistant"。
        :param content: 消息文本。
        """
        if role not in ("user", "assistant"):
            raise ValueError(f"非法 role: {role!r}")
        with self._lock:
            self._messages.setdefault(pet_id, []).append(
                ChatMessage(role=role, content=content, ts=time.time())
            )
            self._save()

    def context_for(self, pet_id: str) -> list[dict]:
        """返回最近 memory_rounds 轮的 [{"role","content"}, ...]（升序，不含 system prompt）。

        :param pet_id: 宠物 id。
        :return: 可拼进 OpenAI messages 的字典列表。
        """
        with self._lock:
            msgs = list(self._messages.get(pet_id, []))
        # 一轮 = user + assistant 两条，取最近 memory_rounds*2 条
        tail = msgs[-self._memory_rounds * 2 :]
        return [{"role": m.role, "content": m.content} for m in tail]

    def all_messages(self, pet_id: str) -> list[ChatMessage]:
        """返回该宠物全量消息快照副本（升序）。

        :param pet_id: 宠物 id。
        :return: ChatMessage 列表副本。
        """
        with self._lock:
            return list(self._messages.get(pet_id, []))

    def _load(self) -> None:
        """从磁盘加载；缺失按空处理；损坏备份为 memory.corrupt-<timestamp>.json 后重新开始，不崩溃。"""
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            backup = self._path.with_name(f"memory.corrupt-{int(time.time())}.json")
            try:
                self._path.replace(backup)
            except OSError:
                pass
            self._messages = {}
            return
        if not isinstance(data, dict):
            self._messages = {}
            return
        messages: dict[str, list[ChatMessage]] = {}
        for pet_id, items in data.items():
            if not isinstance(items, list):
                continue
            parsed: list[ChatMessage] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                role = item.get("role")
                content = item.get("content")
                ts = item.get("ts", 0.0)
                if role in ("user", "assistant") and isinstance(content, str):
                    parsed.append(
                        ChatMessage(role=role, content=content, ts=float(ts) if isinstance(ts, (int, float)) else 0.0)
                    )
            messages[str(pet_id)] = parsed
        self._messages = messages

    def _save(self) -> None:
        """临时文件 + os.replace 原子写入。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            pet_id: [{"role": m.role, "content": m.content, "ts": m.ts} for m in msgs]
            for pet_id, msgs in self._messages.items()
        }
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)
