"""侧边栏对话框骨架：自定义标题栏 + 左侧分页导航 + 右侧内容区。

设置窗口与聊天窗口共用这一套骨架：
- 标题栏是自绘的（可拖动、只有最小化/关闭，无最大化、无系统 icon），颜色跟随主题；
- 左侧导航底色 = 主题色1，选中项 = 主题色2；右侧内容以主题色2 为主（见 theme.py）；
- 换页直接切（不做淡入）：QGraphicsOpacityEffect 会让整页从透明度 0 开始重绘，
  在无边框透明窗口上表现为「右侧主体闪一下透明、露出桌面」，用户明确要它消失。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..theme import Theme
from .qss import content_stylesheet, nav_stylesheet

_TITLE_BAR_H = 36
#: 内容页对象名：页级底色必须用 ID 选择器限定，否则 Qt 会把 `background: …`
#: 当成 `* {…}` 级联给页内所有控件，顶掉 QLineEdit/QSpinBox 的边框与内边距。
PAGE_OBJECT_NAME = "dshDialogPage"


def _title_icon(kind: str, color: str) -> QIcon:
    """QPainter 自绘标题栏按钮图标（不依赖字体字形，任何字体/主题下都可见）。

    :param kind: "min"（横线）或 "close"（叉线）。
    :param color: 线条颜色（取主题导航文字色，保证与标题栏底色对比）。
    """
    pixmap = QPixmap(30, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    cx, cy = 15, 12
    if kind == "close":
        painter.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
        painter.drawLine(cx - 5, cy + 5, cx + 5, cy - 5)
    else:  # "min"
        painter.drawLine(cx - 5, cy, cx + 5, cy)
    painter.end()
    return QIcon(pixmap)


class _TitleBar(QWidget):
    """自绘标题栏：标题 + 最小化 + 关闭；按住空白处拖动窗口（无最大化、无 icon）。"""

    def __init__(self, title: str, theme: Theme, dialog: QDialog) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._drag_from: QPoint | None = None
        self.setFixedHeight(_TITLE_BAR_H)
        # 同上：QWidget 子类需显式声明才绘制样式表背景
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"_TitleBar {{ background: {theme.nav_bg}; border-top-left-radius: 10px;"
            f" border-top-right-radius: 10px; }}"
            f"QLabel {{ color: {theme.nav_text}; font-weight: 700; background: transparent; }}"
            f"QPushButton#titleBarButton {{ color: {theme.nav_text}; background: transparent;"
            f" border: none; border-radius: 6px; font-size: 15px; font-weight: 700; }}"
            f"QPushButton#titleBarButton:hover {{ background: {theme.accent_hover}; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(4)
        title_label = QLabel(title)
        layout.addWidget(title_label, 1)
        # 图标用 QPainter 自绘（全局字体是幼圆，"–"/"×" 字符可能缺字形导致按钮空白）
        self.min_button = QPushButton()
        self.min_button.setObjectName("titleBarButton")
        self.min_button.setIcon(_title_icon("min", theme.nav_text))
        self.min_button.setFixedSize(30, 24)
        self.min_button.setToolTip("最小化")
        self.min_button.clicked.connect(dialog.showMinimized)
        layout.addWidget(self.min_button)
        self.close_button = QPushButton()
        self.close_button.setObjectName("titleBarButton")
        self.close_button.setIcon(_title_icon("close", theme.nav_text))
        self.close_button.setFixedSize(30, 24)
        self.close_button.setToolTip("关闭")
        self.close_button.clicked.connect(dialog.reject)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event) -> None:  # noqa: N802（Qt 命名）
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._dialog.move(event.globalPosition().toPoint() - self._drag_from)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_from = None
        event.accept()


class ThemedDialog(QDialog):
    """无边框圆角 + 自绘标题栏（主题色1 底）的基础对话框；内容塞进 ``content_layout``。"""

    def __init__(
        self,
        title: str,
        theme: Theme,
        parent: QWidget | None = None,
        size: tuple[int, int] | None = (760, 600),
    ) -> None:
        """构造主题对话框。

        :param title: 窗口标题（显示在自绘标题栏上）。
        :param theme: 界面主题（见 theme.theme_for）。
        :param parent: Qt 父控件。
        :param size: 固定尺寸；None 表示不固定（自适应内容）。
        """
        super().__init__(parent)
        self._theme = theme
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if size is not None:
            self.setFixedSize(*size)

        root = QWidget(self)
        root.setObjectName("dshDialogRoot")
        # QWidget 子类默认不绘制样式表背景：不开这个属性，圆角底色根本不画，
        # 无边框透明窗口就会露出桌面（「打开/换页时主体闪透明」的根因之一）
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        self._root_layout = QVBoxLayout(root)
        self._root_layout.setContentsMargins(0, 0, 0, 10)
        self._root_layout.setSpacing(0)
        self.title_bar = _TitleBar(title, theme, self)
        self._root_layout.addWidget(self.title_bar)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(12, 10, 12, 0)
        self._root_layout.addLayout(self.content_layout, 1)
        self.setStyleSheet(
            f"QWidget#dshDialogRoot {{ background: {theme.content_bg};"
            f" border: 2px solid {theme.accent}; border-radius: 12px; }}"
            + content_stylesheet(theme)
        )

    @property
    def theme(self) -> Theme:
        """本窗口使用的主题。"""
        return self._theme


class SidebarDialog(ThemedDialog):
    """左侧分页导航 + 右侧内容区；底部按钮由子类决定。"""

    def __init__(
        self,
        title: str,
        theme: Theme,
        parent: QWidget | None = None,
        nav_width: int = 170,
        size: tuple[int, int] = (760, 600),
        with_buttons: bool = True,
    ) -> None:
        """构造骨架。

        :param title: 窗口标题（显示在自绘标题栏上）。
        :param theme: 界面主题（见 theme.theme_for）。
        :param parent: Qt 父控件。
        :param nav_width: 左侧导航宽度。
        :param size: 初始窗口尺寸（固定默认大小，不提供最大化）。
        :param with_buttons: 是否带「保存 / 取消」按钮（设置类窗口用）。
        """
        super().__init__(title, theme, parent, size=size)

        self._nav = QListWidget()
        self._nav.setFixedWidth(nav_width)
        self._nav.setStyleSheet(nav_stylesheet(theme))
        self._stack = QStackedWidget()
        # 不透明底：换页/重绘期间露出的是内容底色，而不是桌面（避免闪透明）
        self._stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._stack.setStyleSheet(f"QStackedWidget {{ background: {theme.content_bg}; border: none; }}")
        self._nav.currentRowChanged.connect(self._switch_page)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._nav)
        body.addWidget(self._stack, 1)
        self.content_layout.addLayout(body, 1)

        self.buttons: QDialogButtonBox | None = None
        if with_buttons:
            self.buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            self.buttons.setContentsMargins(0, 6, 0, 0)
            self.buttons.accepted.connect(self.accept)
            self.buttons.rejected.connect(self.reject)
            self.content_layout.addWidget(self.buttons)

    def add_page(self, title: str, widget: QWidget) -> None:
        """追加一页（首次追加自动选中）。内容页外边距统一在这里给。"""
        widget.setContentsMargins(16, 10, 12, 0)
        # 每页自己也要不透明：淡入从透明度 0 开始时，露出的是页底色而非透明窗口
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # 关键：选择器必须限定到本页自身（ID 选择器），无选择器的样式表会被 Qt
        # 当成 `* {…}` 级联下去，把页内输入框的 border/padding 全部顶掉（掉样式事故）。
        widget.setObjectName(PAGE_OBJECT_NAME)
        widget.setStyleSheet(f"QWidget#{PAGE_OBJECT_NAME} {{ background: {self.theme.content_bg}; }}")
        self._nav.addItem(title)
        self._stack.addWidget(widget)
        if self._nav.currentRow() < 0:
            self._nav.setCurrentRow(0)

    def select_page(self, index: int) -> None:
        """切到指定页。"""
        if 0 <= index < self._stack.count():
            self._nav.setCurrentRow(index)

    def _switch_page(self, index: int) -> None:
        """换页：直接切栈。

        不做淡入：QGraphicsOpacityEffect 会把整页（含底色）从透明度 0 重绘，
        在无边框透明窗口上会闪一帧透明、露出桌面，用户明确要求去掉。
        """
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)


__all__ = ["SidebarDialog", "ThemedDialog", "hint", "scroll", "vbox"]
