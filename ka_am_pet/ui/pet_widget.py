"""单宠物渲染/命中/拖拽控件（overlay 与 desktop 两种模式共用）。"""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from ka_am_pet.models import PetConfig
from ka_am_pet.world import PetWorld

_CLICK_MAX_MOVE_PX = 6    # 点击与拖拽的位移阈值
_CLICK_MAX_MS = 400       # 点击最长按压时间

_CLICK_ANIM_S = 0.2       # 点击拉伸动画总时长（横拉-回-纵拉-回）
_CLICK_STRETCH = 1.25     # 点击拉伸幅度
_POPUP_S = 0.8            # 心情浮动飘字时长
_FLIP_HALF_S = 0.1        # 镜像翻转单侧（压缩/展开）时长


class PetWidget(QWidget):
    """渲染单只宠物的控件：按心情贴图绘制，提供点击/拖拽命中区。

    控件为 size×size 正方形透明区；物理包围盒（16:9）锚定控件底部。
    点击触发 0.2s「水平拉伸→恢复→垂直拉伸→恢复」动画 + 心情浮动飘字；
    宠物越过屏幕中线时播放「水平压扁→换镜像→展开」翻转动画。
    """

    clicked = Signal(str)                    # 单击（心情浮动 + 动画）
    menu_requested = Signal(str, QPoint)     # 右键菜单（pet_id, 全局坐标）

    def __init__(
        self,
        pet: PetConfig,
        world: PetWorld,
        images: dict[str, QPixmap],
        origin: QPoint | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """构造宠物控件。

        :param pet: 宠物配置。
        :param world: 共享的 PetWorld（读取位置/心情状态）。
        :param images: 心情档位 -> QPixmap 贴图表（缺档位时调用方已回退）。
        :param origin: 世界坐标到控件坐标的原点偏移（overlay 窗口左上角）。
        :param parent: Qt 父控件（overlay 模式为窗口，desktop 模式为 None）。
        """
        super().__init__(parent)
        self._pet_cfg = pet
        self._world = world
        self._images = images
        self._origin = origin or QPoint(0, 0)
        self._level = ""
        self._press_pos: QPoint | None = None
        self._press_at = 0.0
        self._moved = False

        # 动画状态
        self._click_anim_at: float | None = None   # 点击拉伸动画起点
        self._popup_text: str | None = None        # 心情飘字内容
        self._popup_at: float = 0.0                # 飘字起点
        self._mirrored = self._desired_mirror()    # 当前是否镜像
        self._flip_at: float | None = None         # 翻转动画起点
        self._flip_swapped = False                 # 翻转中点是否已换向

        size = pet.size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.sync_geometry()
        self.refresh_image(force=True)

    @property
    def pet_id(self) -> str:
        return self._pet_cfg.id

    def _state(self):
        return self._world.get_pet(self._pet_cfg.id)

    # ---- 绘制与同步 ----

    def refresh_image(self, force: bool = False) -> None:
        """心情档位变化时即时切换贴图（缺图由调用方回退好）。"""
        level = self._world.mood_tracker(self._pet_cfg.id).level
        if force or level != self._level:
            self._level = level
            self.update()

    def sync_geometry(self) -> None:
        """把控件移动到世界位置（图像底部与物理包围盒底对齐）。"""
        state = self._state()
        size = self._pet_cfg.size
        wx = int(state.x)
        wy = int(state.y + state.height - size)
        self.move(wx - self._origin.x(), wy - self._origin.y())

    def _desired_mirror(self) -> bool:
        """宠物中心在世界左半部分时应镜像（面朝屏幕中央）。"""
        state = self._state()
        left, _, right, _ = self._world.bounds
        return (state.x + state.width / 2) < (left + right) / 2

    def play_click_feedback(self) -> None:
        """点击反馈：0.2s 拉伸动画 + 心情浮动飘字（读 tracker.last_delta）。"""
        now = time.monotonic()
        self._click_anim_at = now
        tracker = self._world.mood_tracker(self._pet_cfg.id)
        value = tracker.value
        delta = tracker.last_delta
        sign = f"+{delta:g}" if delta > 0 else f"{delta:g}"
        self._popup_text = f"心情 {sign} → {value:.0f}"
        self._popup_at = now
        self.update()

    def tick(self) -> None:
        """每帧调用：动画推进 + 贴图/位置同步。"""
        # 翻转检测：越线且当前无翻转动画则启动
        desired = self._desired_mirror()
        if desired != self._mirrored and self._flip_at is None:
            self._flip_at = time.monotonic()
            self._flip_swapped = False
        # 翻转中点换向
        if self._flip_at is not None and not self._flip_swapped:
            if time.monotonic() - self._flip_at >= _FLIP_HALF_S:
                self._mirrored = desired
                self._flip_swapped = True
        if self._flip_at is not None and time.monotonic() - self._flip_at >= _FLIP_HALF_S * 2:
            self._flip_at = None
        # 过期动画清理
        if self._click_anim_at is not None and time.monotonic() - self._click_anim_at >= _CLICK_ANIM_S:
            self._click_anim_at = None
        if self._popup_text is not None and time.monotonic() - self._popup_at >= _POPUP_S:
            self._popup_text = None
        self.refresh_image()
        self.sync_geometry()
        if self._click_anim_at is not None or self._flip_at is not None or self._popup_text is not None:
            self.update()

    def _scales(self) -> tuple[float, float]:
        """当前 (scale_x, scale_y)：点击拉伸动画与翻转动画的合成。"""
        now = time.monotonic()
        sx = sy = 1.0
        if self._click_anim_at is not None:
            t = (now - self._click_anim_at) / _CLICK_ANIM_S  # 0..1
            if t < 0.5:
                # 水平拉伸-恢复（三角波）
                sx = 1.0 + (_CLICK_STRETCH - 1.0) * (1.0 - abs(t * 4 - 1.0))
            else:
                # 垂直拉伸-恢复（三角波）
                sy = 1.0 + (_CLICK_STRETCH - 1.0) * (1.0 - abs(t * 4 - 3.0))
        if self._flip_at is not None:
            ft = (now - self._flip_at) / _FLIP_HALF_S  # 0..2
            sx *= abs(1.0 - ft)  # 1→0→1
        return sx, sy

    def paintEvent(self, event) -> None:  # noqa: N802（Qt 命名）
        pixmap = self._images.get(self._level)
        if pixmap is None:
            return
        sx, sy = self._scales()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w = self.width()
        h = self.height()
        scaled = pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # 锚定底边中心：先移到底部中央，再缩放（含镜像翻转），再画
        painter.translate(w / 2, h)
        painter.scale(sx * (-1.0 if self._mirrored else 1.0), sy)
        painter.drawPixmap(int(-w / 2), -h, scaled)
        painter.end()
        self._paint_popup()

    def _paint_popup(self) -> None:
        """心情飘字：白底圆角标签 + 深描边，从头顶区域内上升并淡出。"""
        if self._popup_text is None:
            return
        t = (time.monotonic() - self._popup_at) / _POPUP_S  # 0..1
        # 前 80% 保持不透明，最后 20% 才淡出——保证一眼能看见
        alpha = 1.0 if t < 0.8 else max(0.0, 1.0 - (t - 0.8) / 0.2)
        rise = int(30 * t)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Microsoft YaHei", max(11, self.width() // 17), QFont.Weight.Bold)
        painter.setFont(font)
        # 从控件顶部区域内向上飘：起点 46px，终点 16px，不被窗口裁掉
        line = QRectF(0, 46 - rise, self.width(), 32)
        # 文字实际像素宽度用于画白底标签
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(self._popup_text)
        chip = QRectF(
            (self.width() - text_w) / 2 - 10,
            line.y() + 1,
            text_w + 20,
            line.height() - 2,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, int(225 * alpha)))
        painter.drawRoundedRect(chip, 9, 9)
        # 深色描边（8 方向）+ 填充
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            painter.setPen(QColor(60, 30, 45, int(220 * alpha)))
            painter.drawText(line.translated(dx, dy), Qt.AlignmentFlag.AlignHCenter, self._popup_text)
        painter.setPen(QColor(235, 70, 135, int(255 * alpha)))
        painter.drawText(line, Qt.AlignmentFlag.AlignHCenter, self._popup_text)
        painter.end()

    # ---- 鼠标交互 ----

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._press_at = time.monotonic()
            self._moved = False
            self._world.start_drag(self._pet_cfg.id, self._press_pos.x(), self._press_pos.y())
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.menu_requested.emit(self._pet_cfg.id, event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._press_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            if (pos - self._press_pos).manhattanLength() > _CLICK_MAX_MOVE_PX:
                self._moved = True
            self._world.drag_to(self._pet_cfg.id, pos.x(), pos.y())
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
            self._world.end_drag(self._pet_cfg.id)
            if not self._moved and (time.monotonic() - self._press_at) * 1000 < _CLICK_MAX_MS:
                self.clicked.emit(self._pet_cfg.id)
                self.play_click_feedback()
            self._press_pos = None
            event.accept()
