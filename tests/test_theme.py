"""主题色系统的测试（theme.py 只依赖 QtGui.QColor，可离屏运行）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ka_am_pet import theme
from ka_am_pet.ui import qss


def test_default_theme_is_sky():
    t = theme.theme_for("sky")
    assert t.key == "sky"
    assert t.color1 == "#7fb2e5"
    assert t.color2 == "#ffffff"
    assert theme.theme_for(None).key == "sky"
    assert theme.theme_for("nonsense").key == "sky"


def test_custom_theme_roundtrip():
    key = theme.custom_key("#112233", "#ddeeff")
    t = theme.theme_for(key)
    assert t.color1 == "#112233"
    assert t.color2 == "#ddeeff"
    assert t.label.startswith("自定义")
    # 坏格式回退默认
    assert theme.theme_for("custom:bad").key == "sky"


def test_derived_colors_are_consistent():
    t = theme.theme_for("sky")
    assert t.accent == t.color1
    assert t.bubble_bg == t.color1
    assert t.progress_chunk == t.color1
    assert t.nav_bg == t.color1
    assert t.nav_selected == t.color2
    # 淡蓝底配深字
    assert theme.contrast_text("#7fb2e5") == "#20242e"
    # 深底配浅字
    assert theme.contrast_text("#202532") == "#ffffff"


def test_stylesheets_reference_theme_colors():
    t = theme.theme_for("custom:#336699/#f0f0f0")
    nav = qss.nav_stylesheet(t)
    content = qss.content_stylesheet(t)
    panel = qss.panel_stylesheet(t)
    assert "#336699" in nav and "#f0f0f0" in nav
    assert "#336699" in content
    assert "border-radius: 45px" in panel
    bg, fg = qss.bubble_colors(t)
    assert bg == "#336699"
