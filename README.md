# ka-am-pet

Python 阉割版 Windows 桌宠：心情贴图、点击互动、拖拽甩抛、多宠物碰撞、OpenAI 兼容对话，
支持 overlay / desktop 两种模式，最终打包为桌面 EXE 双击即用。

默认宠物：超天酱（kangel）与糖糖（ame），心情系统四档（happy/smile/sad/angry）实时切换贴图。

## 实例系统与托盘

- 首次启动弹出**启动器**：勾选本次要运行的实例（可多选、可多开同角色）。
- 实例 = 基底角色（kangel/ame）+ 自定义名字 + 尺寸 + 独立人格提示词，存 SQLite：
  `%APPDATA%\ka-am-pet\pets.db`，长期保存，退出时记住各自最后位置。
- 每个实例的对话记忆按实例 id 隔离（`memory.json` 分组），独立提示词拼接到全局 system prompt。
- 程序托管到**系统托盘**：右击托盘图标列出全部实例，可逐只对话/编辑/移除，也可新增实例、切换模式、改全局设置、退出。

## 目录结构

```text
ka_am_pet/        # 主包（ui/ 为唯一依赖 PySide6 的层）
  physics.py      # 甩抛物理（纯 Python）
  collision.py    # 多宠物碰撞（纯 Python）
  mood.py         # 心情系统（纯 Python）
  db.py           # 实例库 SQLite（纯 Python）
  animation.py    # 帧动画 manifest 与状态机（纯 Python）
  world.py        # PetWorld 统一物理世界
  config.py       # 配置加载/校验/原子保存
  services/       # OpenAI 对话 / 记忆持久化（纯 Python）
  ui/             # overlay / desktop / 启动器 / 对话 / 设置窗口
assets/pets/      # {pet}-{mood}.png 心情贴图（640×640 透明底）
tests/            # pytest 测试
```

## 开发启动

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe main.py
```

> 若机器上有失效的系统代理导致 pip 无法联网，先执行
> `$env:NO_PROXY="*"` 清掉代理兜底再安装。

## 玩法

- **单击**宠物：心情随机浮动 −1/+0/+1/+2，Q 弹拉伸小动画 + 飘字提示。
- 打开对话：右键宠物菜单选「对话」，或在托盘菜单里选某只实例的「对话」。
- **拖拽**：跟手弹簧；快速松手甩出抛物线，撞墙反弹、落地摩擦直到停下。
- 宠物走到屏幕左半边会自动镜像转身（压扁→换向→展开动画）。
- **右键**宠物：菜单（心情值 / 对话 / 设置 / 切换模式 / 退出）；全部实例管理在托盘菜单。
- 两只宠物同屏时可互相撞飞（动量守恒，质量 = size²）。

## 心情系统

心情值 0–100，初始 80，随时间缓慢下降（0.1/s）。四档区间：
`[75,100]=happy`、`[50,74]=smile`、`[25,49]=sad`、`[0,24]=angry`。
点击随机 −1/0/+1/+2、拖拽 +15/s、甩抛 +5。档位实时切换贴图，并在对话时追加心情提示词。

## 配置

首次启动生成 `%APPDATA%\ka-am-pet\config.json`（模式/物理参数/宠物列表/OpenAI 设置/心情参数）。
对话记忆存 `%APPDATA%\ka-am-pet\memory.json`，全量保存，只截取最近 N 轮发给模型。

## API 设置

在设置窗口填写 OpenAI 兼容服务的 `base_url` / `api_key` / `model`；
请求 `POST {base_url}/chat/completions`。API Key 以密码形式输入，不写入日志。

## 模式切换

- **overlay**：单一大窗口承载全部宠物，光标不在宠物上时整窗鼠标穿透。
- **desktop**：每只宠物一个独立窗口，共享同一物理世界。
切换无需重启，位置/速度/记忆保留。

## 测试

```powershell
.\venv\Scripts\python.exe -m pytest
```

## 打包

```powershell
.\build_exe.ps1
# 生成 dist\ka-am-pet.exe，复制到 C:\Users\Administrator\Desktop\ka-am-pet.exe
```

## 素材版权

宠物形象来自《主播女孩重度依赖》（NEEDY GIRL OVERDOSE）的超天酱与糖糖，
仅供个人学习把玩，版权归原作所有；发布分发请自备授权或替换原创素材。

## 常见故障

- **双击无窗口/缺 DLL**：确认使用打包后的 EXE；开发运行需先装 requirements-dev.txt。
- **对话报错**：检查 base_url 是否需要翻墙、api_key 是否有效、模型名是否正确。
- **pip 安装卡住**：系统代理失效导致，先 `$env:NO_PROXY="*"` 再安装。
