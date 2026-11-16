"""动作池勾选列表：摸头与摇摆共用同一套「勾选哪些动作」的 UI。

列表每一行是一个动作（显示动作中文名），勾选/取消即可；
勾选结果由调用方用 :func:`ka_am_pet.actions.clean_pool` 规整成合法动作 key 元组。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

from ...models import ACTION_LABELS
from ...theme import Theme

POOL_LIST_NAME = "actionPoolList"
"""对象名：主题样式用 ID 选择器命中它（AGENTS.md §13.7 禁止无选择器样式表）。"""

ROW_H = 28
"""每行高度（px）。"""

MAX_ROWS = 6
"""最多完整显示几行，超出滚动。"""


class ActionPool(QListWidget):
    """动作勾选列表：一行一个动作，可多选。"""

    def __init__(
        self,
        keys: Sequence[str],
        checked: Iterable[str] = (),
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """构造动作池列表。

        :param keys: 全部可选动作 key（顺序即显示顺序）。
        :param checked: 初始勾选的动作 key。
        :param theme: 界面主题；给了才套主题色（离屏/单测可不传）。
        :param parent: Qt 父控件。
        """
        super().__init__(parent)
        self.setObjectName(POOL_LIST_NAME)
        if theme is not None:
            self._apply_theme(theme)
        self.set_keys(keys, checked)

    def _apply_theme(self, theme: Theme) -> None:
        """给列表套白底 + 边框；禁用态显式灰字（否则看起来还能点）。"""
        self.setStyleSheet(
            f"QListWidget#{POOL_LIST_NAME} {{"
            f" background: {theme.input_bg}; border: 1px solid {theme.border};"
            f" border-radius: 6px; padding: 4px; color: {theme.content_text}; }}"
            f"QListWidget#{POOL_LIST_NAME}:disabled {{"
            f" color: {theme.disabled_text}; background: {theme.disabled_bg}; }}"
        )

    def set_keys(self, keys: Sequence[str], checked: Iterable[str] = ()) -> None:
        """重建列表内容（用于新增实例时套用默认动作池）。"""
        checked_set = set(checked)
        self.clear()
        for key in keys:
            item = QListWidgetItem(ACTION_LABELS.get(key, key))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if key in checked_set else Qt.CheckState.Unchecked)
            self.addItem(item)
        self.setFixedHeight(min(len(keys), MAX_ROWS) * ROW_H + 10)

    def checked_keys(self) -> list[str]:
        """当前勾选的动作 key（按列表顺序）。"""
        return [
            self.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.count())
            if self.item(i).checkState() == Qt.CheckState.Checked
        ]


__all__ = ["ActionPool", "MAX_ROWS", "POOL_LIST_NAME", "ROW_H"]
