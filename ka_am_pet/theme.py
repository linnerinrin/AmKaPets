"""界面主题抽象（纯 Python + QtGui  QColor，禁 QtWidgets，可单测）。

设计目标（用户口径）：
- 只有两个可调「主题色」：主题色1 = 左侧导航底色 / 进度条 / 对话气泡；
  主题色2 = 导航选中项 / 右侧内容的主色（占多数）。
- 其余所有颜色（文字、描边、悬停、按压）都由这两个色按明暗推导，保证抽象、可扩展；
- 预设主题在 :data:`THEMES` 登记，用户也可以在设置里用「自定义」选两个颜色；
  配置里存 ``"sky"`` 或 ``"custom:#7fb2e5/#ffffff"``。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor


def _is_color(text: str) -> bool:
    return QColor(text).isValid()


def lighter(color: str, factor: int) -> str:
    return QColor(color).lighter(factor).name()


def darker(color: str, factor: int) -> str:
    return QColor(color).darker(factor).name()


def contrast_text(bg: str) -> str:
    """背景色上可读的文本色：亮底配深字、暗底配白字。"""
    return "#20242e" if QColor(bg).lightnessF() > 0.62 else "#ffffff"


@dataclass(frozen=True)
class Theme:
    """一套界面主题：颜色只存两个源色，其余派生色用属性即时计算。"""

    key: str        # 主题标识（"sky" / "custom:#aabbcc/#ddeeff"）
    label: str      # 中文显示名（设置里的选项文案）
    color1: str     # 主题色1：导航底色 / 进度条 / 对话气泡
    color2: str     # 主题色2：导航选中 / 右侧内容主色（占多数）

    # ---- 派生色（全部由两个源色推导） ----

    @property
    def nav_bg(self) -> str:
        """左侧导航底色。"""
        return self.color1

    @property
    def nav_selected(self) -> str:
        """导航选中项底色。"""
        return self.color2

    @property
    def nav_text(self) -> str:
        return contrast_text(self.color1)

    @property
    def nav_selected_text(self) -> str:
        return contrast_text(self.color2)

    @property
    def content_bg(self) -> str:
        """右侧内容底色 = 主题色2 本体（用户口径：导航/按钮=色1，其他背景=色2）。"""
        return self.color2

    @property
    def content_text(self) -> str:
        """内容文字色：随色2 明暗自动取对比色（色2 选深色时文字变浅）。"""
        return contrast_text(self.color2)

    @property
    def accent(self) -> str:
        """强调色（按钮、进度条、边框高亮）。"""
        return self.color1

    @property
    def accent_hover(self) -> str:
        return lighter(self.color1, 112)

    @property
    def accent_pressed(self) -> str:
        return darker(self.color1, 112)

    @property
    def accent_text(self) -> str:
        return contrast_text(self.color1)

    @property
    def input_bg(self) -> str:
        return "#ffffff"

    @property
    def border(self) -> str:
        return darker(self.color2, 112)

    @property
    def bubble_bg(self) -> str:
        """桌宠对话气泡底色（主题色1）。"""
        return self.color1

    @property
    def bubble_text(self) -> str:
        return contrast_text(self.color1)

    @property
    def progress_chunk(self) -> str:
        """状态面板进度条填充色（主题色1）。"""
        return self.color1

    @property
    def disabled_bg(self) -> str:
        """置灰控件底色：比内容底深一档（能看出「不可改」又不突兀）。"""
        return darker(self.color2, 108)

    @property
    def disabled_text(self) -> str:
        """置灰文字色：在深浅背景上都勉强可读的中灰。"""
        return "#9aa0aa" if QColor(self.color2).lightnessF() > 0.5 else "#8a919e"


#: 预设主题（默认淡蓝/白）。
THEMES: dict[str, Theme] = {
    "sky": Theme(key="sky", label="淡蓝 / 白", color1="#7fb2e5", color2="#ffffff"),
    "sakura": Theme(key="sakura", label="樱粉 / 白", color1="#f2a7c3", color2="#ffffff"),
    "mint": Theme(key="mint", label="薄荷 / 白", color1="#8fd8c0", color2="#ffffff"),
    "dusk": Theme(key="dusk", label="暮紫 / 雾灰", color1="#a99bd8", color2="#f4f4f8"),
    "ink": Theme(key="ink", label="墨蓝 / 雾灰", color1="#5b7fa6", color2="#eef1f5"),
}

DEFAULT_THEME_KEY = "sky"


def custom_key(color1: str, color2: str) -> str:
    """把两个自定义色编码成配置里存的 key。"""
    return f"custom:{color1.lower()}/{color2.lower()}"


def theme_for(key: str | None) -> Theme:
    """按配置 key 取主题；自定义 key（custom:#c1/#c2）与未知 key 都有兜底。"""
    if key:
        preset = THEMES.get(key)
        if preset is not None:
            return preset
        if key.startswith("custom:"):
            body = key[len("custom:"):]
            parts = body.split("/", 1)
            if len(parts) == 2 and _is_color(parts[0]) and _is_color(parts[1]):
                return Theme(key=key, label="自定义", color1=parts[0], color2=parts[1])
    return THEMES[DEFAULT_THEME_KEY]
