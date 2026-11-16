"""启动器窗口：勾选/新建/编辑/删除桌宠实例，决定本次运行哪些实例。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
)

from ka_am_pet import __version__
from ka_am_pet.characters import base_label
from ka_am_pet.db import InstanceDB
from ka_am_pet.models import AppSettings
from ka_am_pet.theme import theme_for
from ka_am_pet.ui.settings_dialog import InstanceSettingsDialog
from ka_am_pet.ui.sidebar import ThemedDialog


class LauncherWindow(ThemedDialog):
    """启动器：列出全部实例，勾选启动；可新建/编辑/删除。"""

    instances_chosen = Signal(list)  # list[PetInstance] 用户勾选要启动的实例

    def __init__(self, db: InstanceDB, settings: AppSettings, parent=None) -> None:
        """构造启动器。

        :param db: 实例库。
        :param settings: 全局配置（主题 + 实例设置对话框回填用）。
        :param parent: Qt 父控件。
        """
        super().__init__(
            f"ka-am-pet 启动器 v{__version__}",
            theme_for(getattr(settings, "theme", "sky")),
            parent,
            size=(520, 470),
        )
        self._db = db
        self._settings = settings

        layout = self.content_layout
        layout.setSpacing(10)  # 列表 / 按钮行 / 启动键之间留呼吸空间，别再挤成一坨
        layout.addWidget(QLabel("勾选要启动的桌宠（可多选）："))

        self.list = QListWidget()
        self.list.setMinimumHeight(180)
        self.list.itemDoubleClicked.connect(lambda _item: self._edit_selected())
        layout.addWidget(self.list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)  # 相邻按钮的圆角不再互相咬出白色缺口
        for text, handler in (
            ("新建", self._create),
            ("编辑", self._edit_selected),
            ("删除", self._delete_selected),
            ("全选", lambda: self._set_all(Qt.CheckState.Checked)),
            ("全不选", lambda: self._set_all(Qt.CheckState.Unchecked)),
        ):
            btn = QPushButton(text)
            btn.setMinimumHeight(32)
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.start_btn = QPushButton("启动选中的桌宠")
        self.start_btn.setMinimumHeight(38)
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(self._start)
        layout.addWidget(self.start_btn)

        self.reload()

    # ---- 数据 ----

    def reload(self) -> None:
        """从 DB 重新加载实例列表。"""
        self.list.clear()
        for inst in self._db.list_all():
            item = QListWidgetItem(f"{inst.name}（{base_label(inst.base)} · {inst.size}px）")
            item.setData(Qt.ItemDataRole.UserRole, inst.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)

    def _selected_ids(self) -> list[str]:
        ids = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def _current_id(self) -> str | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _set_all(self, state: Qt.CheckState) -> None:
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    # ---- 操作 ----

    def _create(self) -> None:
        dlg = InstanceSettingsDialog(self._settings, None, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        result = dlg.result_instance
        self._db.create(
            result.base,
            result.name,
            result.system_prompt,
            result.size,
            overrides=result.overrides,
            passthrough=result.passthrough,
        )
        self.reload()

    def _edit_selected(self) -> None:
        instance_id = self._current_id()
        if instance_id is None:
            return
        inst = self._db.get(instance_id)
        if inst is None:
            return
        dlg = InstanceSettingsDialog(self._settings, inst, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._db.update(dlg.result_instance)
        self.reload()

    def _delete_selected(self) -> None:
        instance_id = self._current_id()
        if instance_id is not None:
            self._db.delete(instance_id)
            self.reload()

    def _start(self) -> None:
        chosen = [inst for inst in self._db.list_all() if inst.id in self._selected_ids()]
        if not chosen:
            self.start_btn.setText("至少勾选一只！")
            return
        self.instances_chosen.emit(chosen)
        self.accept()
