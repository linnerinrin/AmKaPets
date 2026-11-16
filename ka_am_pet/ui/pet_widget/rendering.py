"""渲染 mixin：按心情档位绘制贴图、心情飘字与眼睛按钮。

职责：只做绘制与命中几何（眼睛矩形），动画状态推进在 animation.py；
缩放结果按档位缓存，避免每帧重采样。覆盖模式下眼睛按钮加深底 + 斜杠。
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

from ka_am_pet.ui.pet_widget import constants as C


class PetRenderingMixin:
    """绘制相关逻辑：贴图缓存、paintEvent、飘字与眼睛按钮（由 PetWidget 组合）。"""

    # ---- 贴图缓存 ----

    def _scaled_pixmap(self) -> QPixmap | None:
        """按档位缓存的缩放贴图（只在档位/尺寸变化时重采样）。"""
        pixmap = self._images.get(self._level)
        if pixmap is None:
            return None
        if self._scaled is None or self._scaled_level != self._level:
            self._scaled = pixmap.scaled(
                self.width(),
                self.height(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled_level = self._level
        return self._scaled

    # ---- 主绘制 ----

    def paintEvent(self, event) -> None:  # noqa: N802（Qt 命名）
        """绘制贴图（合成拉伸/翻转/镜像缩放）+ 飘字 + 眼睛按钮。"""
        scaled = self._scaled_pixmap()
        if scaled is None:
            return
        sx, sy = self._scales()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w = self.width()
        h = self.height()
        painter.translate(w / 2, h)
        painter.scale(sx * (-1.0 if self._mirrored else 1.0), sy)
        painter.drawPixmap(int(-w / 2), -h, scaled)
        painter.end()
        self._paint_popup()
        self._paint_eye()

    def _paint_popup(self) -> None:
        """飘字：只画深色描边 + 粉字（无白底），新的在下、旧的往上排。"""
        if not self._popups:
            return
        now = time.monotonic()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._popup_font)
        total = len(self._popups)
        for index, (text, started) in enumerate(self._popups):  # 旧 → 新
            t = (now - started) / C.POPUP_S
            if t >= 1.0:
                continue
            alpha = 1.0 if t < 0.8 else max(0.0, 1.0 - (t - 0.8) / 0.2)
            newer = total - 1 - index
            rise = int(16 * t) + newer * 26
            line = QRectF(0, max(2.0, 46 - rise), self.width(), 32)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor(45, 22, 34, int(215 * alpha)))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                painter.drawText(line.translated(dx, dy), Qt.AlignmentFlag.AlignHCenter, text)
            painter.setPen(QColor(255, 96, 158, int(255 * alpha)))
            painter.drawText(line, Qt.AlignmentFlag.AlignHCenter, text)
        painter.end()

    # ---- 眼睛按钮（画在控件内） ----

    def _eye_progress(self) -> float:
        """眼睛横向进度：0=左侧，1=右侧（镜像时在右），翻转时平滑滑动。"""
        if self._flip_at is None:
            return 1.0 if self._mirrored else 0.0
        t = max(0.0, min(1.0, (time.monotonic() - self._flip_at) / (C.FLIP_HALF_S * 2)))
        start = 1.0 if self._flip_from else 0.0
        end = 1.0 if self._flip_to else 0.0
        eased = t * t * (3.0 - 2.0 * t)
        return start + (end - start) * eased

    def eye_rect(self) -> QRectF:
        """眼睛按钮相对控件的矩形（供命中测试与壳层穿透判断）。"""
        size = float(self._eye_size)
        margin = float(max(C.EYE_MARGIN, self.width() // 40))
        span = self.width() - size - margin * 2.0
        x = margin + self._eye_progress() * span
        return QRectF(x, margin, size, size)

    def eye_contains_global(self, pos: QPoint) -> bool:
        """全局坐标是否落在眼睛按钮上。"""
        return self.eye_rect().contains(QPointF(self.mapFromGlobal(pos)))

    def _paint_eye(self) -> None:
        """画「密码输入框风格」的眼睛开关：描边眼眶 + 实心瞳孔；覆盖模式加深底 + 斜杠。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.eye_rect().adjusted(1, 1, -1, -1)
        passthrough = self.passthrough
        # 底：可交互=浅底，覆盖模式=深底
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(40, 44, 56, 210) if passthrough else QColor(255, 255, 255, 235))
        painter.drawEllipse(rect)
        # 眼眶（杏仁形，近似密码框眼睛图标）
        cx = rect.center().x()
        cy = rect.center().y()
        w = rect.width() * 0.78
        h = rect.height() * 0.46
        eye = QRectF(cx - w / 2, cy - h / 2, w, h)
        ink = QColor(230, 235, 245) if passthrough else QColor(70, 78, 96)
        painter.setPen(QPen(ink, max(1.4, self._eye_size * 0.06)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(eye)
        # 瞳孔
        pupil = min(eye.width(), eye.height()) * 0.42
        painter.setBrush(ink)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - pupil / 2, cy - pupil / 2, pupil, pupil))
        if passthrough:  # 斜杠 = 已隐藏/只看不点
            painter.setPen(QPen(QColor(230, 90, 110, 240), max(1.6, self._eye_size * 0.07)))
            painter.drawLine(
                int(rect.left() + rect.width() * 0.2),
                int(rect.top() + rect.height() * 0.78),
                int(rect.left() + rect.width() * 0.8),
                int(rect.top() + rect.height() * 0.22),
            )
        painter.end()
