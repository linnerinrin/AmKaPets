"""实例库的打开 / 只读修复 / 降级到应急副本逻辑。

职责：只管「拿到一个可写的 SQLite 连接」，不管表结构之外的读写。
原库不可写（沙箱 / 只读盘 / 被其它进程独占）时自动复制到可写目录，
避免启动直接崩溃；降级原因以返回值交给调用方记录。
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import stat
import tempfile
from pathlib import Path

from ka_am_pet.db.schema import setup_schema

_log = logging.getLogger(__name__)


class DatabaseReadOnly(RuntimeError):
    """实例库不可写（权限不足 / 只读盘 / 被其它进程独占）。"""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"实例库无法写入：{path}")
        self.path = path
        self.reason = reason


def looks_readonly(exc: sqlite3.Error) -> bool:
    """判断异常是否是「写不进去」，这类错误可以换目录重试。"""
    text = str(exc).lower()
    return "readonly" in text or "read-only" in text


def clear_readonly(path: Path) -> bool:
    """给库文件补上可写位；改不动（权限不足/沙箱拦截）时返回 False。"""
    try:
        path.chmod(path.stat().st_mode | stat.S_IWRITE)
    except OSError:
        return False
    return True


def sync_copy(original: Path, target: Path) -> None:
    """复制原库到可写位置；目标更新时保持目标（应急库里的改动不丢）。

    用 copyfile 而不是 copy2：copy2 会连「只读」属性一起复制过去，
    应急库反而写不进去。
    """
    if not original.exists():
        return
    if target.exists() and target.stat().st_mtime >= original.stat().st_mtime:
        return
    shutil.copyfile(original, target)
    try:
        target.chmod(target.stat().st_mode | stat.S_IWRITE)
    except OSError:
        pass


def recovery_targets(original: Path) -> list[Path]:
    """应急库候选位置：%LOCALAPPDATA% → %TEMP%。"""
    name = original.name or "pets.db"
    targets: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        targets.append(Path(local) / "ka-am-pet" / name)
    targets.append(Path(tempfile.gettempdir()) / "ka-am-pet" / name)
    try:
        resolved = original.resolve()
    except OSError:
        resolved = original
    return [t for t in targets if t.resolve() != resolved]


def open_database(
    path: Path,
    *,
    allow_repair: bool = True,
    clear_readonly_fn=clear_readonly,
) -> tuple[sqlite3.Connection, Path, str]:
    """打开数据库并建表；写不进去时先试修只读属性，再退到应急副本。

    :param clear_readonly_fn: 可注入的「补可写位」实现（便于测试禁用修复）。
    :returns: (连接, 实际使用的路径, 降级说明)——正常时降级说明为空串。
    """
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        setup_schema(conn)
    except sqlite3.OperationalError as exc:
        conn.close()
        if not looks_readonly(exc):
            raise
        # 最常见的原因之一：文件被设成「只读」属性。能当场修好就不搬家。
        if allow_repair and clear_readonly_fn(path):
            return open_database(path, allow_repair=False, clear_readonly_fn=clear_readonly_fn)
        return _recover(path, exc)
    return conn, path, ""


def _recover(original: Path, cause: sqlite3.Error) -> tuple[sqlite3.Connection, Path, str]:
    """原库写不进去时，复制到可写目录继续用（旧数据不丢）。"""
    errors = [f"{original}: {cause}"]
    for target in recovery_targets(original):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            sync_copy(original, target)
            conn = sqlite3.connect(str(target), timeout=5.0)
            conn.row_factory = sqlite3.Row
            setup_schema(conn)
        except (OSError, sqlite3.Error) as exc:
            errors.append(f"{target}: {exc}")
            continue
        recovered = (
            f"实例库 {original} 无法写入（{cause}），已临时改用 {target}；"
            "请关闭其它正在运行的桌宠实例，或检查该目录写权限后重启。"
        )
        _log.warning(recovered)
        return conn, target, recovered
    raise DatabaseReadOnly(original, "；".join(errors))
