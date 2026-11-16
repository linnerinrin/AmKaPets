"""配置模型、校验、原子保存与首次默认配置。

健壮性规则：
- 配置缺失：创建默认配置。
- 配置字段非法：字段级回退默认值并显示一次非阻塞警告，不让启动失败。
- 未知字段保留或安全忽略，不清掉用户其它配置。
- 多宠物 id 必须唯一；重复时生成唯一 id。
- mode 仅允许 "overlay" / "desktop"，非法回退 "desktop"。
- JSON 损坏：备份后重建默认，不崩溃。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from .models import (
    AppSettings,
    AudioSettings,
    ChatSettings,
    MoodSettings,
    PetConfig,
    PhysicsParams,
    coerce_float,
    coerce_text,
)
from .resources import app_data_dir

APP_DIR_NAME = "ka-am-pet"

#: 配置结构版本：
#: 2 起 mood.decay_per_second 默认 0.5/s（旧版是 0.1/s）；
#: 3 起好感增益改为整数随机区间（摸头 [-1,2]、拖拽/飞行 [-1,1]/s），旧的
#: click_boost / drag_boost_per_second / throw_boost 定值键不再迁移，直接重置为新默认；
#: 4 起拖拽/飞行增益默认区间改为 [0,2]（用户口径），旧默认 [-1,1] 自动升级；
#: 5 起心情自然下降默认改回 0.1/s（用户口径：掉慢点），旧的 0.5/s 自动升级，
#: 同时 audio.sway_mode（单个动作）改为 audio.music_pool（可多选动作池）。
#: 6 起好感数值全部写死（初始 80、下降 0.1/s、摸头/拖拽/飞行区间 [0,2]），
#: 配置里的这些数字一律忽略——旧版本的迁移代码随之删除。
CONFIG_VERSION = 6

_log = logging.getLogger(__name__)

_VALID_MODES = ("overlay", "desktop")


def default_config_path() -> Path:
    """返回用户可写数据目录下的 config.json（默认 %APPDATA%\\ka-am-pet）。"""
    return app_data_dir() / "config.json"


def default_config() -> AppSettings:
    """生成首次启动的默认配置（desktop 模式 + 超天酱/糖糖双宠 + 默认物理/对话设置）。"""
    return AppSettings(
        mode="desktop",
        physics=PhysicsParams(),
        pets=[
            PetConfig(id="kangel", name="超天酱", size=320, x=None, y=None),
            PetConfig(id="ame", name="糖糖", size=320, x=None, y=None),
        ],
        chat=ChatSettings(),
    )


def _warn(msg: str) -> None:
    """非阻塞警告（日志一次；UI 层可另行展示）。"""
    _log.warning("配置字段非法，已回退默认值: %s", msg)


def _parse_physics(raw: Any) -> PhysicsParams:
    if not isinstance(raw, dict):
        if raw is not None:
            _warn("physics")
        return PhysicsParams()
    return PhysicsParams.from_dict(raw)


def _parse_chat(raw: Any) -> ChatSettings:
    if not isinstance(raw, dict):
        if raw is not None:
            _warn("chat")
        return ChatSettings()
    return ChatSettings.from_dict(raw)


def _parse_mood(raw: Any) -> MoodSettings:
    if not isinstance(raw, dict):
        if raw is not None:
            _warn("mood")
        return MoodSettings()
    return MoodSettings.from_dict(raw)


def _parse_audio(raw: Any) -> AudioSettings:
    if not isinstance(raw, dict):
        if raw is not None:
            _warn("audio")
        return AudioSettings()
    return AudioSettings.from_dict(raw)


def _parse_pets(raw: Any) -> list[PetConfig]:
    default = default_config().pets
    if not isinstance(raw, list) or not raw:
        if raw is not None:
            _warn("pets")
        return default
    pets: list[PetConfig] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        pid = item.get("id")
        if not isinstance(pid, str) or not pid:
            pid = "pet"
        if pid in seen:  # 重复 id：生成唯一 id
            base = pid
            n = 2
            while f"{base}-{n}" in seen:
                n += 1
            pid = f"{base}-{n}"
            _warn(f"pets 重复 id -> {pid}")
        seen.add(pid)
        size = int(coerce_float(item.get("size"), 320, 64, 1024))
        x = item.get("x") if isinstance(item.get("x"), (int, float)) and not isinstance(item.get("x"), bool) else None
        y = item.get("y") if isinstance(item.get("y"), (int, float)) and not isinstance(item.get("y"), bool) else None
        pets.append(
            PetConfig(
                id=pid,
                name=coerce_text(item.get("name"), pid),
                size=size,
                x=float(x) if x is not None else None,
                y=float(y) if y is not None else None,
                base=coerce_text(item.get("base"), "", allow_empty=True),
                system_prompt=coerce_text(item.get("system_prompt"), "", allow_empty=True),
            )
        )
    return pets or default


def load_config(path: Path) -> AppSettings:
    """加载配置：缺失建默认、字段非法回退并告警、重复 id 修复、未知字段保留。

    :param path: config.json 路径。
    :return: 校验后的 AppSettings。
    """
    if not path.is_file():
        settings = default_config()
        save_config(settings, path)
        return settings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        backup = path.with_name(f"config.corrupt-{int(time.time())}.json")
        try:
            path.replace(backup)
        except OSError:
            pass
        _log.warning("config.json 损坏，已备份为 %s: %s", backup, exc)
        settings = default_config()
        save_config(settings, path)
        return settings
    if not isinstance(raw, dict):
        _warn("根节点不是对象")
        return default_config()

    mode = raw.get("mode")
    if mode not in _VALID_MODES:
        if mode is not None:
            _warn(f"mode={mode!r}")
        mode = "desktop"

    version = raw.get("version")
    settings = AppSettings(
        mode=mode,
        physics=_parse_physics(raw.get("physics")),
        pets=_parse_pets(raw.get("pets")),
        chat=_parse_chat(raw.get("chat")),
        mood=_parse_mood(raw.get("mood")),
        audio=_parse_audio(raw.get("audio")),
        overlay_opacity=coerce_float(raw.get("overlay_opacity"), 0.92, 0.2, 1.0),
        theme=coerce_text(raw.get("theme"), "sky"),
    )
    if version is not None and (not isinstance(version, (int, float)) or version < CONFIG_VERSION):
        _log.info("旧配置 version=%r 已按 v%d 的写死好感规则重新解析", version, CONFIG_VERSION)
    # 未知字段保留：随 settings 携带，保存时合回
    known = {"version", "mode", "physics", "pets", "chat", "mood", "audio", "overlay_opacity", "theme"}
    settings.unknown_fields = {k: v for k, v in raw.items() if k not in known}  # type: ignore[attr-defined]
    return settings


def save_config(settings: AppSettings, path: Path) -> None:
    """原子保存配置（临时文件 + os.replace）。

    :param settings: 待保存配置。
    :param path: config.json 路径。
    """
    data: dict[str, Any] = dict(getattr(settings, "unknown_fields", {}))
    data.update(
        {
            "version": CONFIG_VERSION,
            "mode": settings.mode,
            "physics": settings.physics.to_dict(),
            "pets": [
                {
                    "id": p.id,
                    "name": p.name,
                    "size": p.size,
                    "x": p.x,
                    "y": p.y,
                    "base": p.base,
                    "system_prompt": p.system_prompt,
                }
                for p in settings.pets
            ],
            "chat": settings.chat.to_dict(),
            "mood": settings.mood.to_dict(),
            "audio": settings.audio.to_dict(),
            "overlay_opacity": round(float(settings.overlay_opacity), 2),
            "theme": settings.theme,
        }
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        # 目录只读/被占用时不让设置保存失败拖垮整个应用
        _log.error("配置无法写入 %s: %s", path, exc)
