"""离屏冒烟：点击宠物后抓屏，确认心情飘字完整可见（用于人工检查）。"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFont, QFontDatabase, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ka_am_pet.config import default_config  # noqa: E402
from ka_am_pet.models import PetConfig  # noqa: E402
from ka_am_pet.ui.pet_widget import PetWidget  # noqa: E402
from ka_am_pet.world import PetWorld  # noqa: E402
from ka_am_pet.world.events import KIND_DRAG, MoodEvent  # noqa: E402

app = QApplication(sys.argv)
# 离屏渲染要手动加载中文字体，否则飘字全是豆腐块
QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\msyh.ttc")
app.setFont(QFont("Microsoft YaHei", 9))
settings = default_config()
world = PetWorld(settings)
world.add_pet(PetConfig(id="kangel", name="超天酱", size=320, base="kangel"))
world.set_bounds((0.0, 0.0, 1920.0, 1080.0))

pixmap = QPixmap(str(ROOT / "assets" / "pets" / "kangel" / "kangel-happy.png"))
assert not pixmap.isNull(), "缺少贴图"
images = {level: pixmap for level in ("happy", "smile", "sad", "angry")}
widget = PetWidget(PetConfig(id="kangel", name="超天酱", size=320, base="kangel"), world, images)
widget.play_click_feedback()  # 单击只播随机动作（不加好感）
# 拖拽/飞行结算飘字（第四轮）：直接喂一条 MoodEvent 验证文案渲染
widget.play_mood_event(MoodEvent(pet_id="kangel", kind=KIND_DRAG, delta=3, value=83.0))
widget.show()
app.processEvents()
for _ in range(6):  # 推进几帧，让飘字上浮到脑袋上方
    widget.tick()
    app.processEvents()
# 产物写临时目录：仓库里不留调试垃圾（见 AGENTS.md 的「调试产物用完即删」）
out = Path(tempfile.gettempdir()) / "ka_am_pet_popup_smoke.png"
widget.grab().save(str(out))
print("saved", out)
