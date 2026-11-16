"""GUI smoke test: start app, tick 3 seconds, screenshot each pet widget."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from ka_am_pet.app import PetApplication

# 产物写临时目录：仓库里不留调试垃圾（见 AGENTS.md 的「调试产物用完即删」）
OUT_DIR = tempfile.gettempdir()


def main() -> int:
    qt_app = QApplication(sys.argv)
    app = PetApplication(qt_app)
    app.start()

    def snap():
        for w in app.shell_widgets():
            try:
                pix = w.grab()
                path = os.path.join(OUT_DIR, f"ka_am_pet_smoke_{w.pet_id()}.png")
                pix.save(path)
                print("saved", path, w.geometry())
            except Exception as e:
                print("grab failed", e)
        qt_app.quit()

    QTimer.singleShot(3000, snap)
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
