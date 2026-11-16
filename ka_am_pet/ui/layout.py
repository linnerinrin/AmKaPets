"""通用布局小工具：灰色说明字、可滚动容器、竖排容器。

为什么单独成模块：这三个函数和「带侧栏的对话框壳」没有关系，却被聊天/全局设置/
实例设置三个对话框反复使用；放在 sidebar.py 里等于让「壳」承担了「工具箱」职责
（SRP），也让 UI 模块之间的依赖方向变糊。
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

__all__ = ["hint", "scroll", "vbox"]


def hint(text: str) -> QLabel:
    """生成灰色小字说明。"""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color:#8a8a96;font-size:11px;")
    return label


def scroll(widget: QWidget) -> QWidget:
    """把内容包进无边框滚动区域，窗口变小时不会挤变形。"""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(widget)
    return area


def vbox(*widgets: QWidget) -> QWidget:
    """把若干控件竖着排进一个容器（供放进滚动区）。"""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 4, 0)
    layout.setSpacing(12)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return container
