"""主题化数值输入框 / 下拉框：关掉 Qt 原生箭头，自己画上/下三角。

为什么不用原生箭头：``theme.content_stylesheet`` 给 QSpinBox/QDoubleSpinBox 加了
border / border-radius / padding 之后，Qt 会走 QStyleSheetStyle 分支，原生上/下箭头
与 QComboBox 的 drop-down 被画成残缺的「⌐」L 形（4x 放大实测，见交接文档「设置页
输入框」事故）。这里把上下按钮 / drop-down 改成透明无边框，箭头由自绘三角接管，
在 Fusion / windowsvista 等样式下表现一致，颜色也与主题的白底输入框相配。

注意不能用 ``ButtonSymbols.NoButtons``：QStyleSheetStyle 在 NoButtons 下会把内部
QLineEdit 算成 1px 宽，数字直接不显示（实测 edit=(0,5,1,19)）。

MRO 红线（AGENTS.md §13.6）：本模块的 mixin 提供 ``paintEvent`` / ``mousePressEvent``
等 Qt 虚函数，类定义里必须排在 Qt 基类之前，否则会被 QWidget 的空实现静默遮蔽。
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox

#: 右侧箭头区宽度（px）。QSS 的 padding-right 比它再宽一点，数字才不会压到箭头上。
ARROW_ZONE_WIDTH = 20

_DIVIDER_COLOR = "#dcdfe5"
_HOVER_BG = "#eef2f7"
_ARROW_COLOR = "#5c6470"
_ARROW_HOVER_COLOR = "#2a2f3a"

#: 上下按钮改成「20px 宽、透明、无边框」：Qt 会照常把数字区让出来（内部 QLineEdit
#: 不会被挤成 1px），但不再画它自己的箭头——箭头由 _ArrowSpinMixin.paintEvent 接管。
_SPIN_STYLE = (
    "QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border;"
    " subcontrol-position: top right; width: " + str(ARROW_ZONE_WIDTH) + "px; border: none;"
    " background: transparent; }\n"
    "QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border;"
    " subcontrol-position: bottom right; width: " + str(ARROW_ZONE_WIDTH) + "px; border: none;"
    " background: transparent; }\n"
    "QSpinBox::up-arrow, QSpinBox::down-arrow, QDoubleSpinBox::up-arrow,"
    " QDoubleSpinBox::down-arrow { image: none; width: 0px; height: 0px; }\n"
    "QSpinBox, QDoubleSpinBox { padding-right: " + str(ARROW_ZONE_WIDTH + 6) + "px; }"
)

#: 下拉框：清掉 Qt 默认的 drop-down 边框（否则在 QSS 描边框内画成残缺的「⌐」L 形），
#: 箭头由 _ChevronComboMixin 自绘。
_COMBO_STYLE = (
    "QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right;"
    " width: 22px; border: none; background: transparent; }\n"
    "QComboBox::down-arrow { width: 0px; height: 0px; }\n"
    f"QComboBox {{ padding-right: {ARROW_ZONE_WIDTH + 6}px; }}"
)


def _triangle(center: QPointF, pointing_up: bool) -> QPolygonF:
    """以 center 为中心构造一个 8x5 的实心三角（点向上或向下）。"""
    dx, dy = 4.0, 2.5 if pointing_up else -2.5
    return QPolygonF(
        [
            QPointF(center.x() - dx, center.y() + dy),
            QPointF(center.x() + dx, center.y() + dy),
            QPointF(center.x(), center.y() - dy),
        ]
    )


class _ArrowSpinMixin:
    """给 QSpinBox/QDoubleSpinBox 补上自绘箭头（mixin，须排在 Qt 基类之前）。"""

    def __init__(self, parent=None) -> None:
        """构造并接管箭头绘制与点击。"""
        super().__init__(parent)
        self.setStyleSheet(_SPIN_STYLE)
        self.setMouseTracking(True)
        self._hover_arrow = 0  # 0=不在箭头区；1=上半（+）；-1=下半（-）
        edit = self.lineEdit()  # 文本区是内部 QLineEdit，右侧留白处的点击也要接住
        if edit is not None:
            edit.setMouseTracking(True)
            edit.installEventFilter(self)

    # ---- 几何 ----

    def _arrow_zone(self) -> QRectF:
        """箭头区（控件右侧一条），坐标为本控件坐标系。"""
        return QRectF(self.width() - ARROW_ZONE_WIDTH, 0, ARROW_ZONE_WIDTH, self.height())

    def _half(self, pos: QPointF) -> int:
        """命中的半边：箭头区上半返回 1、下半返回 -1、其余 0。"""
        if not self._arrow_zone().contains(pos):
            return 0
        return 1 if pos.y() < self.height() / 2 else -1

    # ---- 绘制 ----

    def paintEvent(self, event) -> None:
        """先让 Qt 画框和数字，再叠上箭头区。"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        zone = self._arrow_zone()
        if self._hover_arrow and self.isEnabled():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(_HOVER_BG))
            half = QRectF(zone.x(), zone.y() + 2, zone.width() - 2, zone.height() / 2 - 2)
            if self._hover_arrow < 0:
                half.moveTop(zone.center().y())
            painter.drawRoundedRect(half, 4, 4)
        painter.setPen(QColor(_DIVIDER_COLOR))
        painter.drawLine(QPointF(zone.x(), 4), QPointF(zone.x(), self.height() - 4))
        for direction in (1, -1):
            color = _ARROW_HOVER_COLOR if self._hover_arrow == direction else _ARROW_COLOR
            if not self.isEnabled():
                color = _DIVIDER_COLOR
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            center_y = self.height() * (0.30 if direction > 0 else 0.70)
            painter.drawPolygon(_triangle(QPointF(zone.center().x(), center_y), direction > 0))

    # ---- 交互 ----

    def _step_by_arrow(self, direction: int) -> None:
        """按一次箭头：走一个 singleStep（方向 1=增、-1=减）。"""
        if not self.isEnabled():
            return
        self.stepBy(self.singleStep() * direction)

    def mousePressEvent(self, event) -> None:
        """箭头区按下即步进，其余交给基类（拖动选字等不受影响）。"""
        half = self._half(event.position())
        if half and event.button() == Qt.MouseButton.LeftButton:
            self._step_by_arrow(half)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """悬停到箭头区时高亮对应半边。"""
        self._update_hover(self._half(event.position()))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        """离开控件时清掉箭头高亮。"""
        self._update_hover(0)
        super().leaveEvent(event)

    def _update_hover(self, half: int) -> None:
        """记录悬停半边，变化时重绘（并给出手指光标提示可点）。"""
        if half == self._hover_arrow:
            return
        self._hover_arrow = half
        self.setCursor(Qt.CursorShape.PointingHandCursor if half else Qt.CursorShape.IBeamCursor)
        self.update()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """内部 QLineEdit 覆盖区里的箭头点击：换算到本控件坐标后照常步进。"""
        edit = self.lineEdit()
        if edit is not None and watched is edit:
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove):
                pos = edit.mapTo(self, event.position().toPoint())  # type: ignore[attr-defined]
                half = self._half(QPointF(pos))
                if event.type() == QEvent.Type.MouseMove:
                    self._update_hover(half)
                elif half and event.button() == Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
                    self._step_by_arrow(half)
                    return True
        return super().eventFilter(watched, event)


class SpinBox(_ArrowSpinMixin, QSpinBox):
    """整数输入框（自绘箭头）。"""


class DoubleSpinBox(_ArrowSpinMixin, QDoubleSpinBox):
    """浮点输入框（自绘箭头）。"""


class _ChevronComboMixin:
    """给 QComboBox 画主题化下拉三角（mixin，须排在 Qt 基类之前）。"""

    def __init__(self, parent=None) -> None:
        """构造并接管下拉三角绘制。"""
        super().__init__(parent)
        self.setStyleSheet(_COMBO_STYLE)

    def paintEvent(self, event) -> None:
        """先让 Qt 画框和文字，再在右侧画一个朝下的小三角。"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_ARROW_COLOR if self.isEnabled() else _DIVIDER_COLOR))
        center = QPointF(self.width() - ARROW_ZONE_WIDTH / 2 - 1, self.height() / 2)
        painter.drawPolygon(_triangle(center, False))


class ComboBox(_ChevronComboMixin, QComboBox):
    """下拉框（自绘下拉三角）。"""


__all__ = ["ARROW_ZONE_WIDTH", "ComboBox", "DoubleSpinBox", "SpinBox"]
