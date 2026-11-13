"""离屏冒烟：点击宠物后抓屏，确认心情飘字完整可见（用于人工检查）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ka_am_pet.config import default_config  # noqa: E402
from ka_am_pet.models import PetConfig  # noqa: E402
from ka_am_pet.ui.pet_widget import PetWidget  # noqa: E402
from ka_am_pet.world import PetWorld  # noqa: E402

app = QApplication(sys.argv)
settings = default_config()
world = PetWorld(settings)
world.add_pet(PetConfig(id="kangel", name="超天酱", size=320, base="kangel"))
world.set_bounds((0.0, 0.0, 1920.0, 1080.0))

pixmap = QPixmap(str(ROOT / "assets" / "pets" / "kangel" / "kangel-happy.png"))
assert not pixmap.isNull(), "缺少贴图"
images = {level: pixmap for level in ("happy", "smile", "sad", "angry")}
widget = PetWidget(PetConfig(id="kangel", name="超天酱", size=320, base="kangel"), world, images)
world.click_pet("kangel")
widget.play_click_feedback()
widget.show()
app.processEvents()
out = ROOT / "popup_smoke.png"
widget.grab().save(str(out))
print("saved", out)
