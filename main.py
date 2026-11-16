"""ka-am-pet 入口：构造 QApplication 与 PetApplication 并进入事件循环。"""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from ka_am_pet.app import PetApplication

_log = logging.getLogger(__name__)

#: 全局 UI 字体：幼圆（系统缺失时 Qt 自动回退到可用字体，不报错）。
UI_FONT_FAMILY = "幼圆"


def main() -> int:
    """创建 QApplication 与 PetApplication，启动应用。

    启动过程任何异常都转成中文弹窗（而不是把 traceback 直接甩给用户），
    保证「配置损坏 / 目录不可写」这类问题能被看懂。

    :return: 应用退出码（来自 PetApplication.start()）。
    """
    qt_app = QApplication(sys.argv)
    qt_app.setFont(QFont(UI_FONT_FAMILY, 10))
    # 宠物窗是 Tool 窗、对话窗是临时窗：关掉对话不代表退出应用
    qt_app.setQuitOnLastWindowClosed(False)
    try:
        app = PetApplication(qt_app)
        return app.start()
    except Exception as exc:  # noqa: BLE001 - 顶层兜底，转成可读提示
        _log.exception("启动失败")
        QMessageBox.critical(
            None,
            "ka-am-pet 启动失败",
            f"{type(exc).__name__}: {exc}\n\n详细日志见控制台输出。",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
