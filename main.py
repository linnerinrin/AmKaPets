"""ka-am-pet 入口：构造 QApplication 与 PetApplication 并进入事件循环。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ka_am_pet.app import PetApplication


def main() -> int:
    """创建 QApplication 与 PetApplication，启动应用。

    :return: 应用退出码（来自 PetApplication.start()）。
    """
    qt_app = QApplication(sys.argv)
    # 宠物窗是 Tool 窗、对话窗是临时窗：关掉对话不代表退出应用
    qt_app.setQuitOnLastWindowClosed(False)
    app = PetApplication(qt_app)
    return app.start()


if __name__ == "__main__":
    raise SystemExit(main())
