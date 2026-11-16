"""托盘/宠物右键菜单的共用动作集（app/tray.py:_add_pet_actions）回归测试。

为什么要有这条测试：托盘实例子菜单与宠物右键曾各写一遍「对话 / 实例设置… /
覆盖模式」，第四轮审计把它们收敛成一个方法；本测试锁住三件事——
1. 两种入口给出的前三项完全一致（含顺序）；
2. 只有托盘那条多「移除该实例」；
3. 覆盖模式勾选反映当前状态，点击后确实回调 _set_passthrough。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMenu

from ka_am_pet.app.tray import TrayMixin

_APP = QApplication.instance() or QApplication([])


class _Pet:
    """最小宠物桩：只需要 passthrough 字段。"""

    def __init__(self, passthrough: bool) -> None:
        self.passthrough = passthrough


class _World:
    def __init__(self, pet: _Pet) -> None:
        self._pet = pet

    def get_pet(self, pet_id: str) -> _Pet:
        return self._pet


class _Stub(TrayMixin):
    """收集动作回调的桩，验证菜单项确实接到这些方法上。"""

    def __init__(self, passthrough: bool = False) -> None:
        self.calls: list[tuple[str, object]] = []
        self.world = _World(_Pet(passthrough))

    def _open_chat(self, pet_id: str) -> None:
        self.calls.append(("chat", pet_id))

    def _edit_instance(self, pet_id: str) -> None:
        self.calls.append(("edit", pet_id))

    def _set_passthrough(self, pet_id: str, enabled: bool) -> None:
        self.calls.append(("cover", (pet_id, enabled)))

    def _remove_instance(self, pet_id: str) -> None:
        self.calls.append(("remove", pet_id))


def _labels(menu: QMenu) -> list[str]:
    return [action.text() for action in menu.actions()]


def test_tray_and_pet_menu_share_the_same_three_actions() -> None:
    """两种入口的前三项必须一致，托盘只多一个「移除该实例」。"""
    pet_menu = QMenu()
    tray_sub = QMenu()
    _Stub()._add_pet_actions(pet_menu, "p1")
    _Stub()._add_pet_actions(tray_sub, "p1", include_remove=True)

    assert _labels(pet_menu) == ["对话", "实例设置…", "覆盖模式"]
    assert _labels(tray_sub) == ["对话", "实例设置…", "覆盖模式", "移除该实例"]


def test_cover_action_reflects_passthrough_state() -> None:
    """覆盖模式勾选状态来自当前宠物状态（而不是写死 False）。"""
    menu = QMenu()
    _Stub(passthrough=True)._add_pet_actions(menu, "p1")
    cover = [a for a in menu.actions() if a.text() == "覆盖模式"][0]
    assert cover.isCheckable()
    assert cover.isChecked() is True


def test_cover_toggle_calls_set_passthrough() -> None:
    """取消勾选应回调 _set_passthrough(pet_id, False)。"""
    stub = _Stub(passthrough=True)
    menu = QMenu()
    stub._add_pet_actions(menu, "p1")
    cover = [a for a in menu.actions() if a.text() == "覆盖模式"][0]
    cover.setChecked(False)
    assert ("cover", ("p1", False)) in stub.calls


def test_menu_callbacks_carry_their_pet_id() -> None:
    """每个动作都绑定自己的 pet_id，不会串到别的宠物上。"""
    stub = _Stub()
    menu = QMenu()
    stub._add_pet_actions(menu, "p9", include_remove=True)
    by_text = {action.text(): action for action in menu.actions()}
    by_text["对话"].trigger()
    by_text["实例设置…"].trigger()
    by_text["移除该实例"].trigger()
    assert stub.calls == [("chat", "p9"), ("edit", "p9"), ("remove", "p9")]
