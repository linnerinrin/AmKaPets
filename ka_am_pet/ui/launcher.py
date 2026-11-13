"""启动器窗口：勾选/新建/编辑/删除桌宠实例，决定本次运行哪些实例。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ka_am_pet.db import InstanceDB, PetInstance

# 可选基底角色（assets/pets/<base>/ 下有四档心情贴图）
BASE_CHARACTERS: tuple[tuple[str, str], ...] = (
    ("kangel", "超天酱 (kangel)"),
    ("ame", "糖糖 (ame)"),
)


class InstanceEditDialog(QDialog):
    """新建/编辑单个实例：基底角色、名字、尺寸、独立提示词。"""

    def __init__(self, parent=None, instance: PetInstance | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑实例" if instance else "新建实例")
        self._instance = instance

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.base_combo = QComboBox()
        for base_id, label in BASE_CHARACTERS:
            self.base_combo.addItem(label, base_id)
        if instance is not None:
            idx = self.base_combo.findData(instance.base)
            if idx >= 0:
                self.base_combo.setCurrentIndex(idx)
            self.base_combo.setEnabled(False)  # 基底不可改（换了等于换角色）
        form.addRow("基底角色", self.base_combo)

        self.name_edit = QLineEdit(instance.name if instance else "")
        self.name_edit.setPlaceholderText("给她起个名字")
        form.addRow("名字", self.name_edit)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(120, 640)
        self.size_spin.setSingleStep(20)
        self.size_spin.setValue(instance.size if instance else 320)
        self.size_spin.setSuffix(" px")
        form.addRow("大小", self.size_spin)

        self.prompt_edit = QPlainTextEdit(instance.system_prompt if instance else "")
        self.prompt_edit.setPlaceholderText("这只宠物专属的人格提示词（留空用全局设置）")
        self.prompt_edit.setFixedHeight(90)
        form.addRow("独立提示词", self.prompt_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            self.name_edit.setPlaceholderText("名字不能为空！")
            return
        super().accept()

    # ---- 结果 ----

    @property
    def base(self) -> str:
        return self.base_combo.currentData()

    @property
    def pet_name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def size(self) -> int:
        return self.size_spin.value()

    @property
    def system_prompt(self) -> str:
        return self.prompt_edit.toPlainText().strip()


class LauncherWindow(QDialog):
    """启动器：列出全部实例，勾选启动；可新建/编辑/删除。"""

    instances_chosen = Signal(list)  # list[PetInstance] 用户勾选要启动的实例

    def __init__(self, db: InstanceDB, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ka-am-pet 启动器")
        self._db = db
        self.resize(460, 340)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("勾选要启动的桌宠（可多选）："))

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _item: self._edit_selected())
        layout.addWidget(self.list)

        btn_row = QHBoxLayout()
        for text, handler in (
            ("新建", self._create),
            ("编辑", self._edit_selected),
            ("删除", self._delete_selected),
            ("全选", lambda: self._set_all(Qt.CheckState.Checked)),
            ("全不选", lambda: self._set_all(Qt.CheckState.Unchecked)),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.start_btn = QPushButton("启动选中的桌宠")
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(self._start)
        layout.addWidget(self.start_btn)

        self.reload()

    # ---- 数据 ----

    def reload(self) -> None:
        """从 DB 重新加载实例列表。"""
        self.list.clear()
        for inst in self._db.list_all():
            item = QListWidgetItem(f"{inst.name}（{inst.base} · {inst.size}px）")
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
        dlg = InstanceEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._db.create(dlg.base, dlg.pet_name, dlg.system_prompt, dlg.size)
            self.reload()

    def _edit_selected(self) -> None:
        instance_id = self._current_id()
        if instance_id is None:
            return
        inst = self._db.get(instance_id)
        if inst is None:
            return
        dlg = InstanceEditDialog(self, inst)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            inst.name = dlg.pet_name
            inst.size = dlg.size
            inst.system_prompt = dlg.system_prompt
            self._db.update(inst)
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
