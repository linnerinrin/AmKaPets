"""渲染壳基类：两种运行形态共用的宠物控件装配、每帧推进与生命周期。

overlay 与 desktop 的差别只在「谁承载宠物窗口」——一个铺满虚拟桌面的大窗口，还是
每只宠物一个局部窗口；而**创建控件、转发四个交互信号、每帧 tick 的顺序、销毁逻辑
完全相同**。这些共性集中在本基类，子类只实现 ``_prepare`` / ``_create_widget``
两个钩子，于是「两种壳可互换」（AGENTS.md §2 架构要求 / SOLID-LSP）由继承关系保证，
而不是靠两份长得像的代码碰巧一致。

新增壳种（例如未来做多屏 overlay）只需继承 :class:`PetShell` 并实现上述钩子。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from ka_am_pet.models import PetConfig, PetState
from ka_am_pet.ui.mood_feed import flush_mood_events
from ka_am_pet.ui.pet_widget import PetWidget
from ka_am_pet.world import PetWorld

__all__ = ["PetShell"]


class PetShell(QWidget):
    """渲染壳抽象：持有一组 :class:`PetWidget`，统一转发它们的交互信号。

    子类钩子顺序：``_prepare()`` → 逐只 ``_create_widget()`` → ``_after_widgets()``。
    """

    pet_clicked = Signal(str)                    # 单击（pet_id）
    pat_requested = Signal(str)                  # 双击摸头
    menu_requested = Signal(str, QPoint)         # 右键菜单（pet_id, 全局坐标）
    passthrough_changed = Signal(str, bool)      # 覆盖模式切换

    def __init__(
        self,
        world: PetWorld,
        pet_images: dict[str, dict[str, QPixmap]],
        parent: QWidget | None = None,
    ) -> None:
        """按世界里的宠物逐只造控件并接好信号。

        :param world: 共享的 PetWorld（两种壳共用同一逻辑世界）。
        :param pet_images: pet_id -> (心情档位 -> QPixmap)。
        :param parent: 壳自身的 Qt 父控件。
        """
        super().__init__(parent)
        self._world = world
        self._widgets: list[PetWidget] = []
        self._prepare()
        for pet in world.pets:
            widget = self._create_widget(pet, pet_images.get(pet.pet_id, {}))
            widget.clicked.connect(self.pet_clicked)
            widget.pat_requested.connect(self.pat_requested)
            widget.menu_requested.connect(self.menu_requested)
            widget.passthrough_changed.connect(self.passthrough_changed)
            widget.show()
            self._widgets.append(widget)
        self._after_widgets()

    # ---- 子类钩子 ----

    def _prepare(self) -> None:
        """造控件之前调用：设置窗口标志、几何、坐标原点等（默认无操作）。"""

    def _create_widget(self, pet: PetState, images: dict[str, QPixmap]) -> PetWidget:
        """为一只宠物造控件；父窗口与坐标原点由子类决定。"""
        raise NotImplementedError

    def _after_widgets(self) -> None:
        """全部控件就绪后调用（默认无操作）。"""

    # ---- 共用行为 ----

    def _make_widget(
        self,
        pet: PetState,
        images: dict[str, QPixmap],
        *,
        parent: QWidget | None = None,
        origin: QPoint | None = None,
    ) -> PetWidget:
        """统一的 PetWidget 构造（避免两种壳各写一遍配置映射）。"""
        cfg = PetConfig(id=pet.pet_id, name=pet.pet_id, size=pet.size)
        return PetWidget(cfg, self._world, images, origin=origin, parent=parent)

    @property
    def widgets(self) -> list[PetWidget]:
        """当前全部宠物控件（勿外部增删）。"""
        return self._widgets

    def pet_widget(self, pet_id: str) -> PetWidget | None:
        """按宠物 id 取对应控件（查看状态面板锚点用）；找不到返回 None。"""
        for widget in self._widgets:
            if widget.pet_id == pet_id:
                return widget
        return None

    def tick(self, music_mode: bool = False) -> None:
        """每帧推进：先结算世界事件（飘字），再推进动画与音乐节拍。"""
        flush_mood_events(self._world, self._widgets)
        for widget in self._widgets:
            widget.tick()
            widget.music_tick(music_mode)

    def music_reaction(self) -> None:
        """手动让每只宠物做一次音乐回应（托盘菜单预览用）。"""
        for widget in self._widgets:
            widget.play_music_reaction()

    def close_shell(self) -> None:
        """模式切换时关闭本壳（不退出应用）；世界状态保留。"""
        for widget in self._widgets:
            widget.dispose()
            widget.close()
        self._widgets.clear()
