"""可选基底角色清单（assets/pets/<base>/ 下有四档心情贴图）。"""

from __future__ import annotations

BASE_CHARACTERS: tuple[tuple[str, str], ...] = (
    ("kangel", "超天酱 (kangel)"),
    ("ame", "糖糖 (ame)"),
)


def base_label(base: str) -> str:
    """基底 id -> 展示名；未知基底回退 id 本身。"""
    for base_id, label in BASE_CHARACTERS:
        if base_id == base:
            return label
    return base
