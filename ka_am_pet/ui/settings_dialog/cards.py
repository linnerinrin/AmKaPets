"""「当前状态」区域的状态卡片：一个状态一张卡片，可扩展。

设计（用户口径，第四轮）：取消原来的「好感度」分组，改成「当前状态」容器；
好感度以进度条形式放在里面；以后每加一种状态就新增一个卡片类，
容器按 key 分发刷新数据，不需要改容器本身（OCP）。

刷新协议：``frame.refresh({"mood": {...}, ...})``，卡片从字典里取自己
``key`` 对应的那条数据；缺数据时卡片保持上一次的样子（不报错、不闪）。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...models import MOOD_DECAY

KEY_MOOD = "mood"
"""好感度卡片在状态字典里的 key。"""

LEVEL_LABELS = {"happy": "开心", "smile": "微笑", "sad": "难过", "angry": "生气"}


class StatusCard(QGroupBox):
    """一张状态卡片的基类：固定 ``key`` + 统一的 ``refresh`` 入口。"""

    key: str = ""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """构造卡片。

        :param title: 卡片标题（显示在卡片左上）。
        :param parent: Qt 父控件。
        """
        super().__init__(title, parent)
        self._body = QVBoxLayout(self)
        self._body.setSpacing(6)

    def refresh(self, data: Mapping[str, Any]) -> None:
        """按 key 取本卡片的数据并刷新（子类覆写）。"""
        raise NotImplementedError


class StatusCardFrame(QGroupBox):
    """「当前状态」容器：纵向摆放若干 :class:`StatusCard`。"""

    def __init__(self, title: str = "当前状态", parent: QWidget | None = None) -> None:
        """构造容器。"""
        super().__init__(title, parent)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(8)
        self._cards: dict[str, StatusCard] = {}

    def add_card(self, card: StatusCard) -> None:
        """登记一张卡片（同 key 重复登记时以最后一次为准）。"""
        self._cards[card.key] = card
        self._layout.addWidget(card)

    def card(self, key: str) -> StatusCard | None:
        """按 key 取卡片（测试与调试用）。"""
        return self._cards.get(key)

    def refresh(self, data: Mapping[str, Any]) -> None:
        """把状态字典分发给所有卡片。"""
        for key, card in self._cards.items():
            payload = data.get(key)
            if isinstance(payload, Mapping):
                card.refresh(payload)


class MoodCard(StatusCard):
    """好感度卡片：进度条 + 固定下降速度 + 直播练习开关。"""

    key = KEY_MOOD
    practice_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """构造好感度卡片。"""
        super().__init__("好感度", parent)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        self.bar.setFormat("%v / 100")
        self.level_label = QLabel("—")
        self.decay_label = QLabel(f"每秒 -{MOOD_DECAY:g}（固定）")
        self.practice = QPushButton("直播练习")
        self.practice.setCheckable(True)
        self.practice.setToolTip("开启后好感钉在 100 且不再下降；关闭恢复进入前的值")
        self.practice.toggled.connect(self.practice_toggled.emit)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.level_label)
        row.addWidget(self.decay_label)
        row.addStretch(1)
        row.addWidget(self.practice)
        self._body.addWidget(self.bar)
        self._body.addLayout(row)

    def refresh(self, data: Mapping[str, Any]) -> None:
        """刷新好感值 / 档位 / 直播练习状态。"""
        value = float(data.get("value", 0.0))
        self.bar.setValue(max(0, min(100, int(round(value)))))
        level = str(data.get("level", ""))
        self.level_label.setText(LEVEL_LABELS.get(level, level or "—"))
        practice = bool(data.get("practice", False))
        if self.practice.isChecked() != practice:
            # 阻塞信号：这是外部状态回流，不应该再触发一次切换
            self.practice.blockSignals(True)
            self.practice.setChecked(practice)
            self.practice.blockSignals(False)


__all__ = [
    "KEY_MOOD",
    "LEVEL_LABELS",
    "MoodCard",
    "StatusCard",
    "StatusCardFrame",
]
