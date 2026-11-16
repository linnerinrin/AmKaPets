"""用户数据目录回退探测的测试（不触碰真实 %APPDATA%）。"""

from __future__ import annotations

from ka_am_pet import resources


def test_override_env_is_used(monkeypatch, tmp_path):
    target = tmp_path / "custom"
    monkeypatch.setenv(resources.DATA_DIR_ENV, str(target))
    assert resources.app_data_dir() == target
    assert target.is_dir()
    assert resources.data_dir_note() == ""


def test_fallback_when_preferred_unwritable(monkeypatch, tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("x", encoding="utf-8")  # 拿文件当目录用 → mkdir 必然失败
    monkeypatch.setenv(resources.DATA_DIR_ENV, str(blocker / "data"))
    monkeypatch.setenv("APPDATA", str(blocker / "roaming"))
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    chosen = resources.app_data_dir()

    assert chosen == local / "ka-am-pet"
    assert chosen.is_dir()
    note = resources.data_dir_note()
    assert note and "无法写入" in note


def test_write_probe_rejects_file_path(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    assert resources._is_writable(blocker / "sub") is False
    assert resources._is_writable(tmp_path / "ok") is True
