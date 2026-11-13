# ka-am-pet onefile 打包脚本
$ErrorActionPreference = "Stop"

& .\venv\Scripts\python.exe -m PyInstaller `
  --noconfirm --clean --onefile --windowed `
  --name ka-am-pet `
  --add-data "assets;assets" `
  --paths . `
  main.py

# 验证后复制到桌面：
# Copy-Item .\dist\ka-am-pet.exe C:\Users\Administrator\Desktop\ka-am-pet.exe
