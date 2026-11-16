"""「查看状态」互动的展示控件：状态面板、输入条、对话气泡。

本模块只做控件构建与绘制，不含显隐/跟位逻辑（见 controller.py）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...theme import Theme
from ..qss import bubble_colors, panel_stylesheet

PANEL_MIN_W = 150
PANEL_MAX_W = 280  # 上限内按内容自适应；长名字（「名字（基底）」）靠 wordWrap 换行不裁切
BUBBLE_MAX_W = 280
BAR_MAX_W = 220

# 面板/气泡与桌宠共用的无标题栏置顶小窗 flags
POPUP_FLAGS = (
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
)


class StatusPanel(QWidget):
    """桌宠上方的小状态卡片：姓名、好感进度条、几行属性。"""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("petStatusPanel")
        self.setWindowFlags(POPUP_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(panel_stylesheet(theme))
        self.setMinimumWidth(PANEL_MIN_W)
        self.setMaximumWidth(PANEL_MAX_W)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        self.name_label = QLabel()
        self.name_label.setWordWrap(True)  # 长名字换行显示，不越出面板右边界
        name_font = self.name_label.font()
        name_font.setPointSize(name_font.pointSize() + 2)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        layout.addWidget(self.name_label)

        self.mood_bar = QProgressBar()
        self.mood_bar.setRange(0, 100)
        self.mood_bar.setTextVisible(True)
        layout.addWidget(self.mood_bar)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(2)
        self._rows: dict[str, QLabel] = {}
        for key in ("mood", "music"):
            label = QLabel("-")
            self._rows[key] = label
        form.addRow("档位", self._rows["mood"])
        form.addRow("音乐", self._rows["music"])
        layout.addLayout(form)

    def refresh(self, data: dict[str, str]) -> None:
        """刷新展示内容；data 由应用层组装（名字/好感/档位/音乐）。"""
        self.name_label.setText(data.get("name", ""))
        try:
            value = int(float(data.get("mood_value", "0")))
        except ValueError:
            value = 0
        self.mood_bar.setValue(max(0, min(100, value)))
        self.mood_bar.setFormat(f"{value} / 100")
        self._rows["mood"].setText(data.get("mood", "-"))
        self._rows["music"].setText(data.get("music", "-"))


class ChatInputBar(QWidget):
    """桌宠底部的输入条：回车或按钮发送；发送后自动清空。"""

    message_sent = Signal(str)

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("petStatusPanel")  # 复用同一套圆角卡片样式
        self.setWindowFlags(POPUP_FLAGS)
        self.setStyleSheet(panel_stylesheet(theme))
        self.setMaximumWidth(BAR_MAX_W)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        self.input = QLineEdit()
        self.input.setPlaceholderText("说点什么…")
        self.input.returnPressed.connect(self._send)
        layout.addWidget(self.input, 1)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self._send)
        layout.addWidget(self.send_button)

    def set_busy(self, busy: bool) -> None:
        """请求期间禁用输入，避免连发。"""
        self.input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.send_button.setText("…" if busy else "发送")

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.message_sent.emit(text)


class SpeechBubble(QWidget):
    """桌宠上方的对话气泡：底色=主题色1，说完话后点一下就消失。"""

    dismissed = Signal()

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(POPUP_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        bg, fg = bubble_colors(theme)
        self._bg = QColor(bg)
        self._fg = QColor(fg)
        self._text = ""
        self.setMaximumWidth(BUBBLE_MAX_W)

    def set_text(self, text: str) -> None:
        """设置气泡文字并按内容自适应大小。"""
        self._text = text
        metrics = self.fontMetrics()
        width = min(BUBBLE_MAX_W, max(90, metrics.horizontalAdvance(text) + 32))
        lines = max(1, metrics.horizontalAdvance(text) // max(1, width - 32) + 1)
        height = lines * (metrics.lineSpacing() + 2) + 24
        self.setFixedSize(width, min(220, height))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802（Qt 命名）
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)
        painter.fillPath(path, self._bg)
        painter.setPen(self._fg)
        painter.drawText(self.rect().adjusted(12, 8, -12, -8), Qt.TextFlag.TextWordWrap, self._text)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.dismissed.emit()
        self.hide()
        event.accept()
