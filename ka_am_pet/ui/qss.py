"""主题样式表生成：把 :class:`~ka_am_pet.theme.Theme` 的派生色拼成 QSS 文本。

为什么单独成模块：这些函数**只产出字符串**，与「主题数据/派生色计算」是两件事，
混在 theme.py 里会导致该文件超过 AGENTS.md §13.1 的 300 行硬上限；拆出来后
theme.py 只负责数据，本模块只负责渲染细节，改样式不必碰数据。
"""

from __future__ import annotations

from ..theme import Theme, lighter

__all__ = ["bubble_colors", "content_stylesheet", "nav_stylesheet", "panel_stylesheet"]


def nav_stylesheet(theme: Theme) -> str:
    """左侧导航列表样式（底色=主题色1，选中=主题色2）。"""
    return f"""
QListWidget {{
    background: {theme.nav_bg};
    border: none;
    outline: none;
    padding: 10px 8px;
}}
QListWidget::item {{
    color: {theme.nav_text};
    padding: 10px 14px;
    border-radius: 8px;
    margin: 2px 0;
}}
QListWidget::item:hover {{
    background: {theme.accent_hover};
}}
QListWidget::item:selected {{
    background: {theme.nav_selected};
    color: {theme.nav_selected_text};
    font-weight: 600;
}}
/* 启动器实例列表的勾选框：画在主题色1 上，必须显式给白底+色1描边才看得见 */
QListWidget::indicator {{
    width: 16px; height: 16px;
}}
QListWidget::indicator:unchecked {{
    border: 2px solid {theme.accent_pressed}; border-radius: 4px; background: #ffffff;
}}
QListWidget::indicator:checked {{
    border: 2px solid {theme.accent_pressed}; border-radius: 4px; background: {theme.accent};
}}
QListWidget::indicator:disabled {{
    border: 2px solid {theme.disabled_text}; background: {theme.disabled_bg};
}}
"""


def content_stylesheet(theme: Theme) -> str:
    """对话框主体样式：右侧内容以主题色2 为主，输入/按钮跟随主题色。"""
    return f"""
QDialog, QWidget#dshDialogRoot {{
    background: {theme.content_bg};
    color: {theme.content_text};
}}
QGroupBox {{
    font-size: 14px;
    font-weight: 700;
    border: 1px solid {theme.border};
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 10px;
    background: {theme.content_bg};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {theme.content_text};
}}
QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {theme.input_bg};
    border: 1px solid {theme.border};
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: {theme.accent};
    selection-color: {theme.accent_text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {theme.accent};
}}
QPushButton {{
    background: {theme.accent};
    color: {theme.accent_text};
    border: none;
    border-radius: 6px;
    padding: 6px 18px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {theme.accent_hover}; }}
QPushButton:pressed {{ background: {theme.accent_pressed}; }}
QPushButton:disabled {{ background: {theme.border}; color: {theme.disabled_text}; }}
/* 输入类置灰：底色比内容底深一档 + 灰字，一眼能看出「这栏不可改」 */
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: {theme.disabled_bg};
    color: {theme.disabled_text};
    border: 1px solid {theme.border};
}}
QCheckBox, QRadioButton {{ spacing: 6px; color: {theme.content_text}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px;
}}
QCheckBox::indicator:unchecked {{
    border: 2px solid {theme.accent}; border-radius: 4px; background: {theme.input_bg};
}}
QCheckBox::indicator:unchecked:hover {{
    background: {theme.accent_hover};
}}
QCheckBox::indicator:checked {{
    border: 2px solid {theme.accent_pressed}; border-radius: 4px; background: {theme.accent};
}}
QCheckBox::indicator:disabled {{
    border: 2px solid {theme.disabled_text}; background: {theme.disabled_bg};
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {theme.disabled_text}; }}
QProgressBar {{
    background: {theme.input_bg};
    border: 1px solid {theme.border};
    border-radius: 7px;
    text-align: center;
    height: 14px;
}}
QProgressBar::chunk {{
    background: {theme.progress_chunk};
    border-radius: 7px;
}}
QScrollArea {{ border: none; background: transparent; }}
QTabWidget::pane {{ border: none; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: {theme.input_bg}; color: {theme.content_text}; border: 1px solid {theme.border}; }}
"""


def panel_stylesheet(theme: Theme) -> str:
    """桌宠状态面板（圆角白底卡片）样式。"""
    return f"""
QWidget#petStatusPanel {{
    background: {lighter(theme.color2, 102)};
    border: 1px solid {theme.border};
    border-radius: 45px;
}}
QLabel {{ background: transparent; color: #2a2f3a; }}
QProgressBar {{
    background: {theme.input_bg};
    border: 1px solid {theme.border};
    border-radius: 7px;
    text-align: center;
    height: 12px;
}}
QProgressBar::chunk {{ background: {theme.progress_chunk}; border-radius: 7px; }}
QLineEdit {{
    background: {theme.input_bg};
    border: 1px solid {theme.border};
    border-radius: 10px;
    padding: 3px 8px;
}}
QPushButton {{
    background: {theme.accent};
    color: {theme.accent_text};
    border: none;
    border-radius: 10px;
    padding: 4px 12px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {theme.accent_hover}; }}
QPushButton:pressed {{ background: {theme.accent_pressed}; }}
"""


def bubble_colors(theme: Theme) -> tuple[str, str]:
    """对话气泡的 (底色, 文本色)：底色=主题色1。"""
    return theme.bubble_bg, theme.bubble_text
