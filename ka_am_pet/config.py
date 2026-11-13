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

from .audio import MAX_INTERVAL_SECONDS, MIN_INTERVAL_SECONDS
from .models import AppSettings, AudioSettings, ChatSettings, MoodSettings, PetConfig, PhysicsParams

APP_DIR_NAME = "ka-am-pet"

_log = logging.getLogger(__name__)

_VALID_MODES = ("overlay", "desktop")


def default_config_path() -> Path:
    """返回 %APPDATA%\\ka-am-pet\\config.json。"""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    return root / APP_DIR_NAME / "config.json"


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


def _num(value: Any, default: float, lo: float | None = None, hi: float | None = None) -> float:
    """字段级数值校验：非法回退默认值，可选范围钳制。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    v = float(value)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def _str(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _warn(msg: str) -> None:
    """非阻塞警告（日志一次；UI 层可另行展示）。"""
    _log.warning("配置字段非法，已回退默认值: %s", msg)


def _parse_physics(raw: Any) -> PhysicsParams:
    default = PhysicsParams()
    if not isinstance(raw, dict):
        if raw is not None:
            _warn("physics")
        return default
    return PhysicsParams(
        gravity=_num(raw.get("gravity"), default.gravity, 0.0, 10000.0),
        restitution=_num(raw.get("restitution"), default.restitution, 0.0, 1.0),
        ground_friction=_num(raw.get("ground_friction"), default.ground_friction, 0.0, 100.0),
        ceiling_bounce=bool(raw.get("ceiling_bounce", default.ceiling_bounce)),
        throw_power=_num(raw.get("throw_power"), default.throw_power, 0.0, 10.0),
        pet_collision=bool(raw.get("pet_collision", default.pet_collision)),
    )


def _parse_chat(raw: Any) -> ChatSettings:
    default = ChatSettings()
    if not isinstance(raw, dict):
        if raw is not None:
            _warn("chat")
        return default
    return ChatSettings(
        base_url=_str(raw.get("base_url"), default.base_url).rstrip("/"),
        api_key=raw.get("api_key") if isinstance(raw.get("api_key"), str) else "",
        model=_str(raw.get("model"), default.model),
        system_prompt=raw.get("system_prompt") if isinstance(raw.get("system_prompt"), str) else default.system_prompt,
        memory_rounds=int(_num(raw.get("memory_rounds"), default.memory_rounds, 1, 100)),
        timeout_seconds=int(_num(raw.get("timeout_seconds"), default.timeout_seconds, 5, 300)),
    )


def _parse_mood(raw: Any) -> MoodSettings:
    default = MoodSettings()
    if not isinstance(raw, dict):
        if raw is not None:
            _warn("mood")
        return default
    prompts_raw = raw.get("prompts")
    prompts = (
        {str(k): v for k, v in prompts_raw.items() if isinstance(v, str)}
        if isinstance(prompts_raw, dict)
        else {}
    )
    return MoodSettings(
        initial=_num(raw.get("initial"), default.initial, 0.0, 100.0),
        decay_per_second=_num(raw.get("decay_per_second"), default.decay_per_second, 0.0, 100.0),
        click_boost=_num(raw.get("click_boost"), default.click_boost, 0.0, 100.0),
        drag_boost_per_second=_num(raw.get("drag_boost_per_second"), default.drag_boost_per_second, 0.0, 1000.0),
        throw_boost=_num(raw.get("throw_boost"), default.throw_boost, 0.0, 100.0),
        prompts=prompts,
    )


def _parse_audio(raw: Any) -> AudioSettings:
    default = AudioSettings()
    if not isinstance(raw, dict):
        if raw is not None:
            _warn("audio")
        return default
    return AudioSettings(
        enabled=bool(raw.get("enabled", default.enabled)),
        interval_seconds=_num(
            raw.get("interval_seconds"),
            default.interval_seconds,
            MIN_INTERVAL_SECONDS,
            MAX_INTERVAL_SECONDS,
        ),
    )


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
        size_raw = item.get("size")
        size = int(_num(size_raw, 320, 64, 1024))
        x = item.get("x") if isinstance(item.get("x"), (int, float)) and not isinstance(item.get("x"), bool) else None
        y = item.get("y") if isinstance(item.get("y"), (int, float)) and not isinstance(item.get("y"), bool) else None
        pets.append(
            PetConfig(
                id=pid,
                name=_str(item.get("name"), pid),
                size=size,
                x=float(x) if x is not None else None,
                y=float(y) if y is not None else None,
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

    settings = AppSettings(
        mode=mode,
        physics=_parse_physics(raw.get("physics")),
        pets=_parse_pets(raw.get("pets")),
        chat=_parse_chat(raw.get("chat")),
        mood=_parse_mood(raw.get("mood")),
        audio=_parse_audio(raw.get("audio")),
    )
    # 未知字段保留：随 settings 携带，保存时合回
    known = {"mode", "physics", "pets", "chat", "mood", "audio"}
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
            "mode": settings.mode,
            "physics": {
                "gravity": settings.physics.gravity,
                "restitution": settings.physics.restitution,
                "ground_friction": settings.physics.ground_friction,
                "ceiling_bounce": settings.physics.ceiling_bounce,
                "throw_power": settings.physics.throw_power,
                "pet_collision": settings.physics.pet_collision,
            },
            "pets": [
                {"id": p.id, "name": p.name, "size": p.size, "x": p.x, "y": p.y} for p in settings.pets
            ],
            "chat": {
                "base_url": settings.chat.base_url,
                "api_key": settings.chat.api_key,
                "model": settings.chat.model,
                "system_prompt": settings.chat.system_prompt,
                "memory_rounds": settings.chat.memory_rounds,
                "timeout_seconds": settings.chat.timeout_seconds,
            },
            "mood": {
                "initial": settings.mood.initial,
                "decay_per_second": settings.mood.decay_per_second,
                "click_boost": settings.mood.click_boost,
                "drag_boost_per_second": settings.mood.drag_boost_per_second,
                "throw_boost": settings.mood.throw_boost,
                "prompts": settings.mood.prompts,
            },
            "audio": {
                "enabled": settings.audio.enabled,
                "interval_seconds": settings.audio.interval_seconds,
            },
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
