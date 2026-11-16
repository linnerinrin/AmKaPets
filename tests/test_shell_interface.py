"""渲染壳接口回归：desktop / overlay 必须共用 PetShell 的公共行为（LSP）。

为什么需要这条测试：这两种壳曾各自实现一遍「造控件 + 连信号 + tick + 关闭」，
一致性只能靠巧合；AGENTS.md §2 要求「渲染壳可互换」，本轮改成继承 PetShell 后，
一旦有人在某一侧重新覆盖 tick/close_shell/信号，两份实现就会再次分叉。
这里直接断言「公共行为只在基类定义、子类只实现承载钩子」。
"""

from __future__ import annotations

from ka_am_pet.ui.desktop import DesktopWindow
from ka_am_pet.ui.overlay import OverlayWindow
from ka_am_pet.ui.shell_base import PetShell

SHARED_METHODS = ("tick", "music_reaction", "pet_widget", "widgets")
SIGNALS = ("pet_clicked", "pat_requested", "menu_requested", "passthrough_changed")
SHELL_HOOKS = {"_prepare", "_create_widget", "_after_widgets"}
# 承载差异之外，overlay 还需要：关自己的大窗口、调整层不透明度、做命中测试
ALLOWED_OVERRIDES = {
    "DesktopWindow": set(),
    "OverlayWindow": {"close_shell", "set_opacity", "nativeEvent", "_accepts"},
}


def test_both_shells_are_pet_shells() -> None:
    """两种壳都必须是 PetShell 子类（否则「可互换」无从谈起）。"""
    assert issubclass(DesktopWindow, PetShell)
    assert issubclass(OverlayWindow, PetShell)


def test_public_behaviour_is_inherited_not_redefined() -> None:
    """公共方法只允许在基类定义；子类重写即视为接口分叉。"""
    for cls in (DesktopWindow, OverlayWindow):
        for name in SHARED_METHODS:
            assert name not in cls.__dict__, f"{cls.__name__} 不应重写 {name}()"


def test_signal_contract_is_inherited() -> None:
    """四个交互信号只在基类声明，两种壳对外暴露同一份契约。"""
    for cls in (DesktopWindow, OverlayWindow):
        for name in SIGNALS:
            assert name not in cls.__dict__, f"{cls.__name__} 不应重新声明信号 {name}"
            assert hasattr(cls, name)


def test_subclasses_only_override_shell_hooks() -> None:
    """子类只允许覆盖承载钩子（+ 各自承载所需的少量方法），保证差异最小。"""
    for cls in (DesktopWindow, OverlayWindow):
        overridden = {
            name
            for name, value in cls.__dict__.items()
            if callable(value) and not name.startswith("__")
        } - SHELL_HOOKS
        allowed = ALLOWED_OVERRIDES[cls.__name__]
        assert overridden <= allowed, (
            f"{cls.__name__} 覆盖了不该覆盖的方法：{overridden - allowed}"
        )
