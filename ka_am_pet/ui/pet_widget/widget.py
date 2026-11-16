"""PetWidget 主体：组装渲染/动画/交互 mixin，负责构造、几何同步与生命周期。

控件为 size×size 正方形透明区；物理包围盒（16:9）锚定控件底部。
职责边界（配合包 docstring）：本文件只装配各 mixin 并处理 Qt 生命周期，
具体动作状态机在 animation.py，绘制在 rendering.py，鼠标/穿透在 interaction.py。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QWidget

from ka_am_pet.audio import SwayScheduler
from ka_am_pet.models import PetConfig
from ka_am_pet.ui.pet_widget import constants as C
from ka_am_pet.ui.pet_widget.animation import PetAnimationMixin
from ka_am_pet.ui.pet_widget.interaction import PetInteractionMixin
from ka_am_pet.ui.pet_widget.rendering import PetRenderingMixin
from ka_am_pet.world import PetWorld


class PetWidget(PetAnimationMixin, PetRenderingMixin, PetInteractionMixin, QWidget):
    """渲染单只宠物的控件：按心情贴图绘制，提供点击/拖拽命中区。

    单击播放随机动作（点头摇摆/左右摇摆，不加好感），双击间隔判定摸头（才加好感）；
    宠物越过屏幕中线（或音乐左右摇摆）时播放「水平压扁→换镜像→展开」翻转。

    注意：mixin 必须列在 QWidget **前面**——paintEvent/mousePressEvent 等
    Qt 虚函数按 MRO 查找，QWidget 在前会遮蔽 mixin 实现，窗口将完全不绘制
    （曾经的表现：窗体存在但整只宠物不可见）。
    """

    clicked = Signal(str)                    # 单击（动作 + 计数；面板由应用层决定开不开）
    pat_requested = Signal(str)              # 双击摸头
    menu_requested = Signal(str, QPoint)     # 右键菜单（pet_id, 全局坐标）
    passthrough_changed = Signal(str, bool)  # 覆盖模式切换（pet_id, 是否覆盖）

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
        self._scaled: QPixmap | None = None
        self._scaled_level = ""
        self._press_pos: QPoint | None = None
        self._press_at = 0.0
        self._moved = False
        self._last_click_at = 0.0  # 上一次单击（松开）时间：双击摸头按两次点击间隔判定

        # 动作状态：拉伸类动作起点 / 镜像翻转队列
        self._stretch_at: float | None = None
        self._stretch_s = 0.2
        self._stretch_kind = "stretch"  # 当前拉伸曲线："stretch" 点头 / "squish" 摸头压扁
        self._flip_at: float | None = None
        self._flip_from = False
        self._flip_to = False
        self._flip_swapped = False
        self._flip_left = 0                # 还需要再翻几次（左右摇摆=2，偶数次回原位）
        self._popups: list[tuple[str, float]] = []
        self._popup_font = QFont("Microsoft YaHei", max(11, pet.size // 17), QFont.Weight.Bold)

        # 镜像状态
        self._mirrored = self._desired_mirror()
        self._auto_mirror = self._mirrored

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

        # 音乐摇摆节拍（间隔来自实例/全局音乐设置）
        self._sway = SwayScheduler(self._world.audio_for(pet.id).interval_seconds)

        # 眼睛按钮尺寸（画在控件里，不额外开窗口）
        self._eye_size = max(C.EYE_MIN, min(C.EYE_MAX, size // 12))

    @property
    def pet_id(self) -> str:
        """宠物实例 id。"""
        return self._pet_cfg.id

    def _state(self):
        """从 PetWorld 取本宠物的最新状态（位置/拖拽/覆盖标记）。"""
        return self._world.get_pet(self._pet_cfg.id)

    @property
    def passthrough(self) -> bool:
        """是否处于覆盖模式（只看得见、点不到）。"""
        return bool(self._state().passthrough)

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
        target_x = wx - self._origin.x()
        target_y = wy - self._origin.y()
        if self.x() != target_x or self.y() != target_y:
            self.move(target_x, target_y)

    def _desired_mirror(self) -> bool:
        """宠物中心在世界左半部分时应镜像（面朝屏幕中央）。"""
        state = self._state()
        left, _, right, _ = self._world.bounds
        return (state.x + state.width / 2) < (left + right) / 2

    # ---- 生命周期 ----

    def dispose(self) -> None:
        """关闭控件前的清理（保持接口，壳层统一调用）。"""
        self._popups.clear()

    def closeEvent(self, event) -> None:  # noqa: N802（Qt 命名）
        self.dispose()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802（Qt 命名）
        """尺寸变化后清掉缩放贴图缓存，下次绘制时按新尺寸重采样。"""
        self._scaled = None
        super().resizeEvent(event)
