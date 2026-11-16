# ka-am-pet — Python 阉割版桌宠施工说明

> 本文档是独立工作区 Agent 的唯一任务基线。目标：参考 `dsh-pet`，用 Python 实现一个 Windows 桌宠，只保留 **点击随机动画、拖拽甩抛、多宠物碰撞、OpenAI Chat Completions 对话**，支持 **overlay 与桌面模式**，最终打包成桌面 EXE，双击即用。
>
> 原项目仅供阅读参考，不要求运行原项目，不修改原项目文件。

## 1. 项目与交付目标

- 项目目录：`C:\Users\Administrator\PycharmProjects\ka-am-pet`
- 已有虚拟环境：`venv\Scripts\python.exe`，CPython 3.11.4。
- 运行平台：Windows 10/11 x64，优先保证 Windows 体验，不实现 macOS/Linux 兼容层。
- 技术选型：**Python 3.11 + PySide6 + requests + PyInstaller + pytest**。
- 所有动画、物理、UI 更新只能在 Qt 主线程执行；网络请求必须放入 worker 线程，通过 Qt Signal 回主线程。
- 最终生成：`C:\Users\Administrator\Desktop\ka-am-pet.exe`，无需安装 Python、Node、DSH 或 Electron，双击即用。
- 用户配置及对话记忆写入 `%APPDATA%\ka-am-pet\`，首次启动自动创建，不依赖开发机绝对路径。

### 必做范围

1. 至少一只默认宠物，支持配置多只同屏。
2. 点击宠物随机播放回应动画。
3. 拖拽跟手、松手估算初速、甩抛、重力、边界反弹、地面摩擦、停止。
4. 多宠物碰撞：动量守恒、质量与 `size²` 成正比、恢复系数 0.995、切向速度保留。
5. 对话窗口，调用 **OpenAI 兼容的 Chat Completions API**，支持自定义 `base_url` / `api_key` / `model` / `system_prompt`。
6. 对话记忆持久化，完整保存、只截取最近 N 轮发给模型。
7. `overlay` 与 `desktop` 两种运行形态可切换。
8. 默认动画、配置缺失、未配置 API Key、网络失败都不能导致程序崩溃。
9. 物理与碰撞纯函数必须有 pytest 测试。
10. EXE 打包及干净启动验证。
11. 心情系统：心情值 0–100，随时间线性下降；按值分四档（happy / smile / sad / angry），同时影响宠物外观贴图与对话 system prompt；点击与拖拽提高心情值。

### 明确不做

不要扩展成原项目完整复刻，以下均不做：余额、碎碎念、系统通知、表情包选图、积分、弹弓、屏幕漫游、pet pack、斜杠命令、Electron、DSH 插件接口、Web 服务、Safari/mov、右键级联动画分类菜单。

## 2. 两种运行形态的精确定义

### overlay 模式

- 一个覆盖虚拟桌面的无边框、透明、置顶 Qt 窗口，统一承载全部宠物。
- 空白区域必须鼠标穿透；宠物身体命中区可点击和拖拽。
- 所有宠物共享同一坐标系，天然支持多宠物碰撞。
- 推荐 Qt flags：`FramelessWindowHint | WindowStaysOnTopHint | Tool`，透明背景使用 `WA_TranslucentBackground`。
- Windows 鼠标穿透可用 `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE`，但**宠物命中区必须恢复接收输入**。若区域级穿透不稳定，采用保守方案：只在明确无宠物命中的拖拽/点击路径切换穿透，并写测试/手动验证记录；不允许做成全屏拦截所有鼠标输入的窗口。

### desktop 模式

- 每只宠物一个独立的无边框、透明、置顶局部窗口，窗口尺寸为宠物包围盒加少量气泡余量。
- 窗口随宠物位置移动；非宠物区域不拦截输入。
- 多窗口共享同一个逻辑时钟和物理世界，不能各自跑独立碰撞世界。
- 模式切换后位置、速度、对话记忆保留，不能重启进程才生效。

### 架构要求

- 渲染壳可不同，**物理世界、宠物状态、动画状态机、对话服务必须共用**。
- 建议统一由 `PetWorld` 保存全部宠物的逻辑位置、速度、动画状态，由 60Hz 左右的 `QTimer` 驱动。
- 用真实时间差积分，`dt` 限制为最大 0.05 秒；高速运动按最大 8px 位移细分，单帧最多 64 子步。

## 3. 推荐目录结构

允许按实现需要微调，但职责边界必须保留：

```text
ka-am-pet/
  AGENTS.md
  pyproject.toml 或 requirements.txt / requirements-dev.txt
  README.md
  main.py
  ka_am_pet/
    __init__.py
    app.py                 # 应用启动、模式切换、组件装配
    config.py              # 配置模型、校验、原子保存、首次默认配置
    models.py              # PetState / PhysicsParams / ChatMessage 等数据类
    physics.py             # 纯 Python 甩抛、弹簧、积分、细分
    collision.py           # 纯 Python 多宠物碰撞
    animation.py           # 帧动画资源、随机动画选择、状态机
    mood.py                # 纯 Python 心情值/档位/衰减/增益与提示词映射
    world.py               # PetWorld，多宠物统一更新
    resources.py           # 源码/PyInstaller 双模式资源路径
    ui/
      overlay.py
      desktop.py
      pet_widget.py
      chat_dialog.py
      settings_dialog.py
    services/
      openai_chat.py       # Chat Completions 请求与结构化错误
      memory.py            # 全量 JSON 记忆，线程安全快照
  assets/
    pets/main/idle/...     # PNG 帧序列 + manifest.json
    pets/main/happy/...
    pets/main/shy/...
    pets/main/tsundere/...
  scripts/
    convert_assets.py      # 可选：webm → PNG 帧的开发工具，不进运行时依赖
  tests/
    test_physics.py
    test_collision.py
    test_config.py
    test_memory.py
    test_animation.py
    test_mood.py
  build_exe.ps1
```

## 4. 动画实现约束

原版使用 VP9-alpha WebM。**不要假设 Qt QMovie 能可靠播放透明 WebM**，也不要把 OpenCV 当 UI 渲染框架。

采用稳妥方案：每个动作是 PNG 帧序列，配套 `manifest.json`：

```json
{
  "name": "happy",
  "fps": 24,
  "loop": false,
  "frames": ["001.png", "002.png"],
  "width": 640,
  "height": 360
}
```

- 默认至少有 `idle` 循环动画和 `happy` / `shy` / `tsundere` 三个点击回应动画。
- 点击时非等概率或等概率随机均可，但不要连续重复上一段（只有一段时除外）。
- 回应动画结束后回到 `idle`；新点击可打断旧回应。
- 动画按帧时间推进，不能依赖“定时器每次刚好触发一次”。
- 资源缩放到宠物 `size`，保持 16:9，不产生明显锯齿。
- 宠物被拖拽/飞行时仍可播放当前动画；阉割版无需专门飞行动画。
- 如使用原版素材，开发期可用 `ffmpeg -i input.webm -vf fps=24 frame_%03d.png` 转帧。发布包只包含实际用到的动作，避免把 122MB 原包全部塞入 EXE。
- 素材版权/来源在 README 说明；若无法合法复用，则制作简单原创占位动画，接口与验收不变。

## 5. 甩抛物理（必须按此实现）

坐标为宠物包围盒左上角，y 向下；速度 px/s。宠物高度 `h = size * 9 / 16`。

### 拖拽跟手

- 按下后记录指针偏移，拖拽目标 = 当前指针位置 − 偏移。
- 每轴使用过阻尼弹簧：
  - `SPRING_K = 200`
  - `SPRING_C = 30`
  - `v += ((target - x) * K - v * C) * power * dt`
  - `x += v * dt`
- 保存最近 200ms 指针轨迹样本 `(t_ms, x, y)`。

### 松手初速

- 若最后样本距松手超过 150ms，温柔放下，速度清零。
- 估算窗口取最近 150ms；窗口不足 20ms 则原地放下。
- 端点平均速度 `base_v = (p1-p0)/span`。
- 分段采样最小 dt 为 8ms，过密样本向前合并，取分段峰值速度。
- `speed = (0.5 * base_speed + 0.5 * peak_speed)`。
- 末段仍在加速时，加速度增益最多 60%：`accel_ref=8000`。
- 软限速：`soft_clamp(s) = 3600 * (1 - exp(-s/3600))`。
- 最后乘 `throw_power`；低于 `500px/s` 不抛，原地停下。
- 方向使用端点平均速度方向；方向长度近零时原地放下。

### 飞行积分与边界

默认参数：

```text
gravity = 1400 px/s²
restitution = 0.78
ground_friction = 2.5 /s
ceiling_bounce = true
throw_power = 1.0
pet_collision = true（本项目要求可演示多宠物碰撞，默认开启）
```

每步：

1. `dt = clamp(dt, 0, 0.05)`。
2. `vy += gravity * dt; x += vx * dt; y += vy * dt`。
3. 左右越界：位置夹回，`vx = ±abs(vx) * restitution`，方向朝屏内。
4. 顶部越界：仅当 `ceiling_bounce=true` 时夹回并反弹，否则允许飞出后靠重力落回。
5. 落地：`y=max_y`，`vx *= max(0, 1-ground_friction*dt)`；`|vy|<40` 则 `vy=0`，否则 `vy=-abs(vy)*restitution`。
6. 贴地且 `|vy|<1`、`|vx|<15` 时停止飞行。
7. 一帧位移超过 8px 时细分为 `ceil(travel/8)` 步，最多 64 步。

首版边界使用所有屏幕的虚拟桌面并集即可；若某屏任务栏可用工作区不同，优先使用 Qt `availableGeometry()`。**不要求复刻原版复杂的多屏空洞探测。**

### Q 弹可选但推荐

如实现，只做垂直缩放并锚定脚底：点击压至 55%，220ms 回弹；轻落地最低压至 80%，重落地 55%。此项不是核心验收门槛，不能因此拖延基础功能。

## 6. 多宠物碰撞（必须按此实现）

- 使用宠物身体矩形或包围盒做相交检测，配置可统一使用 `QRectF` 等价的纯数据矩形。
- 仅当至少一方处于飞行状态时处理；但被撞静止宠物也必须获得速度并进入飞行状态。
- 质量 `m = size²`。
- 碰撞法向为两宠物包围盒中心连线。
- 中心重合时跳过本帧，避免除零。
- 相对速度法向投影 `vrel = (v_fly-v_hit)·n`；`vrel<=0` 表示正在分离，不重复弹跳。
- 恢复系数 `e=0.995`。
- 法向速度重分配：

```text
v1n2 = ((m1-e*m2)*v1n + (1+e)*m2*v2n)/(m1+m2)
v2n2 = ((m2-e*m1)*v2n + (1+e)*m1*v1n)/(m1+m2)
```

- 切向速度不变：最终速度 = 原切向分量 + 新法向分量。
- 同一对宠物同帧只处理一次；两个窗口也必须共享该逻辑。
- 不要求连续碰撞检测，但 8px 子步必须用于降低穿透。

## 6.5 心情系统（必须按此实现）

心情为每只宠物独立的数值系统，纯 Python 实现在 `mood.py`，禁 Qt，可单测。

### 心情值

- 取值范围 `0–100`，初始值 `80`。
- 随时间**线性下降**：默认 `decay_per_second = 0.1`（约 13 分钟从 80 降到 0），由 `PetWorld.update(dt)` 统一按真实时间差推进，配置可调。
- **点击**宠物 `+click_boost`（默认 8）；**拖拽中**按拖拽距离或时间增益（默认 `drag_boost_per_second = 15`，拖拽每秒 +15）；松手甩抛成功额外 `+throw_boost`（默认 5）。
- 数值始终钳制在 `[0, 100]`。

### 档位划分（value → mood）

| 心情值 | 档位 | 含义 |
|---|---|---|
| 75–100 | `happy` | 开心 |
| 50–74 | `smile` | 微笑 |
| 25–49 | `sad` | 难过 |
| 0–24 | `angry` | 生气 |

边界值归较高档（75→happy，50→smile，25→angry 的反例：25→sad；即区间 `[75,100] [50,74] [25,49] [0,24]`，含左端点）。

### 外观与提示词联动

- 素材命名 `{pet}-{mood}.png`（现有 `assets/pets/kangel/` 与 `assets/pets/ame/` 下各四张：happy/smile/sad/angry）；档位切换时贴图立即更换；缺图回退 `happy` 档贴图再回退 idle 占位帧，不崩溃。
- 心情档位作为基础外观；点击回应动画播放期间可暂时覆盖显示，播完回到当前心情档贴图。
- 对话 system prompt 末尾追加心情描述（每档一句，可在配置 `mood.prompts` 覆盖），例如 angry 档："你现在心情很差，说话带刺但不超过两句话。" 默认四句由 `mood.py` 提供常量。
- 配置示例新增（可全缺省）：

```json
"mood": {
  "initial": 80,
  "decay_per_second": 0.1,
  "click_boost": 8,
  "drag_boost_per_second": 15,
  "throw_boost": 5,
  "prompts": {"happy": "", "smile": "", "sad": "", "angry": ""}
}
```

- 心情值**不持久化**到磁盘：每次启动回到 `initial`（阉割版不做跨会话心情记忆）。

## 7. 对话功能

### 设置项

首次生成 `%APPDATA%\ka-am-pet\config.json`，至少包含：

```json
{
  "mode": "desktop",
  "physics": {
    "gravity": 1400,
    "restitution": 0.78,
    "ground_friction": 2.5,
    "ceiling_bounce": true,
    "throw_power": 1.0,
    "pet_collision": true
  },
  "pets": [
    {"id": "main", "name": "小胖鱼", "size": 320, "x": null, "y": null}
  ],
  "chat": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "system_prompt": "你是桌面上的可爱桌宠，回答自然简短。",
    "memory_rounds": 5,
    "timeout_seconds": 45
  }
}
```

- API Key 不得硬编码、不得写入日志、不得在 README 提交真实凭据。
- 设置界面允许修改并保存 Key；输入框使用密码显示。
- `base_url` 是 OpenAI 兼容服务根地址，最终请求 `POST {base_url}/chat/completions`，自动去掉末尾 `/`。
- Header：`Authorization: Bearer <api_key>`、`Content-Type: application/json`。
- Body：`model`、OpenAI `messages` 数组；可设置 `temperature=0.8`，不依赖 response_format/tools/stream。
- 使用 `requests.Session`，显式 timeout，处理 HTTP 非 2xx、JSON 缺字段、空 choices、连接错误、超时。
- 正确解析 `data["choices"][0]["message"]["content"]`；错误以中文显示在对话窗口，不能只在控制台输出。
- 请求期间禁用发送按钮并显示“思考中…”，结束后恢复；允许关闭窗口但不能销毁后台结果导致崩溃。
- 不提供 Key 时仍可打开对话窗口，提示去设置填写；其余动画与物理功能完全可用。

### 记忆

- 文件：`%APPDATA%\ka-am-pet\memory.json`。
- 按宠物 id 分组，每条包含 `role` / `content` / `ts`。
- 用户消息与助手成功回复全量追加，不自动删除；失败回复不写入。
- 每次请求只携带该宠物最近 `memory_rounds` 轮（一轮=user+assistant），前面加 system prompt。
- JSON 损坏时备份为 `memory.corrupt-<timestamp>.json` 后重新开始，不崩溃。
- 写文件采用临时文件 + replace，避免中途退出损坏。

## 8. 配置与资源健壮性

- 配置缺失：创建默认配置。
- 配置字段非法：字段级回退默认值并显示一次非阻塞警告，不让启动失败。
- 未知字段保留或安全忽略，不能清掉用户其它配置。
- 多宠物 id 必须唯一；重复时生成唯一 id。
- 默认位置：主屏右下角，保留约 24px 横向和 100px 纵向边距；位置为空或完全不可见时回默认位置。
- PyInstaller 资源访问统一用 `resources.py`：
  - 源码运行：项目根目录。
  - 冻结运行：`sys._MEIPASS`（onefile）或可执行文件资源目录。
- 用户可写文件绝不能写进 `sys._MEIPASS`。

## 9. 依赖与工程规范

建议使用：

```text
PySide6>=6.7,<7
requests>=2.32,<3
```

开发依赖：

```text
PyInstaller>=6,<7
pytest>=8,<9
```

- 使用项目现有 `venv\Scripts\python.exe -m pip ...`，不要污染系统 Python。
- 优先标准库 dataclasses / typing / json / pathlib / math。
- 核心逻辑保持纯函数，不为了“看起来高级”引入 asyncio、numpy、OpenCV、Qt Multimedia。
- 代码中避免 Qt import 混入 `physics.py` / `collision.py` / `memory.py`，保证可单测。
- 错误处理明确，不用裸 `except: pass`。
- README 写清：开发启动、配置、API 设置、模式切换、测试、打包、常见故障。

## 10. 测试要求

至少覆盖：

1. 软限速单调且不超过 3600。
2. 低速松手不抛，快速松手产生有限初速。
3. 重力使 vy 增大，落地恢复系数正确，最终可静止。
4. `ceiling_bounce=false` 不夹回顶部。
5. `dt` 上限与高速细分合理。
6. 等质量正碰近似交换法向速度，切向不变。
7. 不同质量碰撞满足一维动量关系（考虑 e=0.995），分离状态不重复碰撞。
8. 中心重合不抛异常。
9. 默认配置生成、非法值回退、重复宠物 id 修复。
10. 记忆全量保存、上下文截断、损坏 JSON 备份恢复。
11. 动画随机不连续重复、回应后回 idle。
12. 心情值线性衰减与钳制、四档边界映射、点击/拖拽/甩抛增益、缺图回退与提示词映射。

网络单测 mock `requests`，不得在测试中调用真实 API。

## 11. 打包与验收

提供 `build_exe.ps1`，建议先使用 onefile：

```powershell
& .\venv\Scripts\python.exe -m PyInstaller `
  --noconfirm --clean --onefile --windowed `
  --name ka-am-pet `
  --add-data "assets;assets" `
  --paths . `
  main.py
# 验证后复制 dist\ka-am-pet.exe 到 C:\Users\Administrator\Desktop\ka-am-pet.exe
```

若 PNG 资源导致 onefile 启动过慢或超过合理体积，允许改为 onedir，但桌面必须有可直接启动的快捷方式，并在 README 说明，不能只交付一个依赖开发目录的脚本。

### 最终手动验收清单

- [ ] 双击桌面 EXE 后出现宠物，无控制台黑窗、无缺失 DLL/资源报错。
- [ ] idle 正常循环，点击能随机播放至少三种回应并回 idle。
- [ ] 拖动跟手，慢放停下，快甩沿抛物线飞行、反弹、落地、最终停止。
- [ ] 两只宠物同屏，一只甩向另一只，两者按质量与速度弹开，静止方也会飞。
- [ ] overlay 与 desktop 均可运行，切换无需重启；overlay 不整屏吞鼠标输入。
- [ ] 不配 API Key 时提示清晰，程序其余功能可用。
- [ ] 配置有效 OpenAI 兼容服务后可完成一次真实对话；失败有中文错误。
- [ ] 重启后记忆仍在，请求只携带最近 N 轮。
- [ ] 移动配置/记忆目录到非开发环境路径语义仍正确；资源路径不依赖 PyCharm。
- [ ] 心情值随时间下降、点击/拖拽上升，四档贴图与对话语气同步切换。
- [ ] `venv\Scripts\python.exe -m pytest` 全绿。

## 12. 工作方式与完成定义

0. **改动前先对齐（用户明确要求）**：收到一轮新需求后，先用自己的话复述一遍需求，对模糊点给出建议并**多提问**，等用户确认后再动手；如果评估后认为某条做不到或代价过大，要**明确告诉用户**（但仍应尽可能先尝试，不要直接放弃）。
1. 先搭可运行最小骨架：单宠物 + idle + 点击回应。
2. 再加甩抛纯函数和测试，然后接入 UI。
3. 再加多宠物与碰撞，确保两种模式共享世界。
4. 最后接对话、设置、记忆，并做打包。
5. 每一步实际运行测试；GUI 自动化不可行时，用手动验收记录替代，不要声称未验证的功能已经验证。
6. 最终回复应列出：修改文件、测试命令与结果、EXE 完整路径、真实对话是否实测、任何剩余限制。

完成定义不是“代码写完”，而是 **桌面 EXE 可启动、四项核心功能可用、两种模式可切换、测试全绿、交付路径明确**。

## 13. 代码架构规范：模块化、低耦合与 SOLID（用户明确要求）

> 本节为强制工程规范。任何任务完成后必须依据本节逐条自检，并在回复中说明自检结果。

### 13.1 文件规模红线

- 单个 `.py` 文件**目标不超过 200 行，硬上限 300 行**；超过 300 行即视为架构异味，必须拆分，不允许出现 600+ 行的「上帝文件」。
- 函数目标不超过 30 行；类目标不超过 200 行。超过时优先考虑职责拆分而非压缩空行。
- 禁止用「都放一起方便改」为理由合并模块。

### 13.2 模块化：一个模块对应一个软件包，而非一个上帝文件

- 以第 3 节目录结构为基线：`physics/`、`collision/`、`animation/`、`mood/`、`services/`、`ui/` 等各为一个职责单一的包/模块。
- 每个模块只暴露明确的公共接口（`__all__` 或文档字符串声明），内部实现细节不外泄。
- 分层依赖单向：`ui/` → `world.py` → `physics.py` / `collision.py` / `mood.py` / `services/`；**纯逻辑层（physics / collision / mood / memory / config）禁止 import Qt 或反向依赖 UI**。
- 模块间通过数据类（`models.py`）与显式接口通信，不共享可变全局状态，不互相读内部字段。

### 13.3 SOLID 落地要求

- **SRP（单一职责）**：一个文件/类只做一件事。例如 `openai_chat.py` 只发请求与解析，不碰 UI、不写文件。
- **OCP（开闭）**：新增动画动作、心情档位、聊天后端时以「新增类/数据」扩展，而不是修改既有分支逻辑。
- **LSP（里氏替换）**：子类可替换父类使用；overlay 与 desktop 渲染壳必须实现同一渲染接口，可互换。
- **ISP（接口隔离）**：调用方只依赖自己用到的接口；不出现「大而全」的胖接口类。
- **DIP（依赖倒置）**：上层依赖抽象而非具体实现。例如 `ChatDialog` 依赖「聊天服务协议」，由装配处（`app.py`）注入 `OpenAIChatService` 或 Mock 实现；副作用（文件、网络、时钟）一律注入，便于测试。

### 13.4 注释与可读性（面向用户阅读）

- 每个公共模块、类、函数必须有 docstring：说明**做什么、为什么这么做、输入输出**，而不是复述代码。
- 关键物理公式、碰撞公式、心情档位映射等处必须带行内注释标明出处与单位（如 `px/s`、`e=0.995` 对应 AGENTS.md 第 6 节）。
- 命名表意：不用 `tmp`、`data2`、`flag` 一类无意义命名；常量集中定义并注释含义。
- 复杂逻辑用「分步小函数 + 注释」表达，不堆长表达式。

### 13.5 每次任务完成后的架构自检清单（必做）

完成任何代码任务后，逐条检查并在最终回复中给出结论：

1. 本次改动后的文件是否都 ≤ 300 行？超出的列出拆分计划。
2. 是否新增/维持了正确的模块边界？有没有纯逻辑层 import Qt、UI 反向依赖等违规？
3. 是否符合 SOLID（重点：单一职责、依赖注入、渲染壳可互换）？
4. 公共接口与关键公式是否都有注释？
5. `venv\Scripts\python.exe -m pytest` 是否全绿？

不满足任一条时，先修正再交付；确实无法立刻满足的，必须明确写出原因与补救计划，不得隐瞒。

### 13.6 Qt mixin 的 MRO 红线（血泪教训，必守）

- **任何提供 Qt 虚函数（`paintEvent` / `mousePressEvent` / `timerEvent` 等）的 mixin，在类定义中必须排在 Qt 基类（如 `QWidget`）之前**：
  `class PetWidget(PetAnimationMixin, ..., QWidget)` ✅；
  `class PetWidget(QWidget, PetAnimationMixin, ...)` ❌。
- 原因：PySide6 按 MRO 分派这些虚函数，`QWidget` 自带的空实现若排在前，会**静默遮蔽** mixin 的实现——窗口能创建、可见、样式正常，但从不绘制、点击无响应，且无任何报错（2026-11-15「宠物不可见」事故的根因）。
- 回归防线：`tests/test_widget_mro.py` 已固化该顺序；以后新增 mixin 拆分时同步补断言。

### 13.7 给控件 setStyleSheet 必须带选择器（血泪教训，必守）

- `widget.setStyleSheet(f"background: {color}; border: none;")` 这种**没有选择器的声明**，Qt 会当成
  `* { … }` **级联给所有子控件**，把 `theme.content_stylesheet` 里 QLineEdit / QSpinBox 的白底、
  1px 边框、内边距全部顶掉——输入框看起来「失去样式但文字还在」(2026-11-16 事故)。
- 正确写法：先 `widget.setObjectName(PAGE_OBJECT_NAME)`，再
  `setStyleSheet(f"QWidget#{PAGE_OBJECT_NAME} {{ background: {bg}; }}")`，只影响这一个容器。
- 回归防线：`ka_am_pet/ui/sidebar.py` 的 `PAGE_OBJECT_NAME = "dshDialogPage"` + `add_page()`。

### 13.8 QSS 描边会毁掉 Qt 原生 spin 箭头 / combo 下拉框（血泪教训，必守）

- 只要 `content_stylesheet` 给 QSpinBox/QDoubleSpinBox 加了 border / border-radius / padding，
  Qt 就走 QStyleSheetStyle 分支，原生上/下箭头被画成残缺的「⌐」L 形；QComboBox 的 drop-down
  同理（右侧一条断掉的 L 边框）。
- **不要用 `ButtonSymbols.NoButtons` 去掉箭头**：QStyleSheetStyle 会把内部 QLineEdit 算成 1px 宽，
  数字直接不显示（实测 `lineEdit().geometry() == (0, 5, 1, 19)`）。
- 唯一稳定做法（已封装在 `ka_am_pet/ui/fields.py`）：保留 UpDownArrows，用 QSS 把 `::up-button` /
  `::down-button` / `::drop-down` 设成「20px 宽、`border: none`、透明」，把 `::up-arrow` /
  `::down-arrow` 设成 `image: none; width: 0`，再由混入类 `paintEvent` 自绘三角。这样内部
  QLineEdit 恢复 `(0, 5, 219, 19)`，数字不被遮挡。
- QSS 里**不要**用 `image: url(绝对路径)` 引 PNG 资源：Windows 反斜杠路径会让整张样式表
  解析失败（`Could not parse stylesheet`），静默不生效。需要图标就自绘。
- 回归防线：`tests/test_widget_mro.py` 的 `test_arrow_field_mixins_precede_qt_bases` /
  `test_chevron_combo_mixin_precedes_qt_base`。

### 13.9 配置只存在实例里；心情数值是常量（第四轮定型，必守）

- **没有「跟随全局」**：`PetOverrides`（历史命名，语义已是「该实例自己的完整设置」）持
  `physics: PhysicsParams`、`chat: ChatSettings`、`music: AudioSettings`、`pat_pool: tuple[str, ...]`。
  不要重新引入 `None = 继承` 或 `is_empty()` 这类语义——旧数据库的空 `overrides_json` 由
  `PetOverrides.from_dict(raw, fallback)` 回落默认值，`dump_overrides()` 恒写完整 JSON。
- **心情数值全部写死**：`models/mood.py` 的 `MOOD_INITIAL=80.0`、`MOOD_DECAY=0.1`、
  `PAT_RANGE/DRAG_RANGE/FLIGHT_RANGE=(0,2)` 是唯一来源，`MoodSettings.from_dict` 只读 `prompts`，
  界面上只展示不给改。改数值请改常量，不要恢复配置读取。
- `AppSettings.mood` 只作为「新建实例 / 心情提示词」的载体；`PetWorld._resolve()` 直接
  `replace(overrides.physics/music)`，不再有 `resolve_physics/resolve_audio/resolve_mood`。
- **结算飘字走事件**：拖拽/飞行期间 `PetWorld` 用 `_drag_delta/_flight_delta` 累计增量，
  结束时 `flush_mood_event()` 产出一条 `MoodEvent`（增量为 0 不发），壳层每帧
  `drain_events()` → `ka_am_pet/ui/mood_feed.py` → `PetWidget.play_mood_event()`。
  新增「结束时提示」类需求一律复用这条事件通道，不要在 UI 层自己算差值。
- **直播练习**：`MoodTracker.set_practice(on)` 快照当前值并钉 100，退出恢复；
  `PetWorld.practice_on/set_practice` 转发。心情卡片的按钮经 app 层回调，不直接碰 tracker。
- **状态卡片要可扩展**：`ui/settings_dialog/cards.py` 里 `StatusCard`（类属性 `key` + `refresh(data)`）
  + `StatusCardFrame.add_card/refresh` 按 key 分发；新增状态就新写一个子类塞进 frame，
  不要往对话框里塞 if/else。
- 回归防线：`tests/test_config.py::test_mood_numbers_are_always_fixed_constants`、
  `tests/test_db.py::TestInstanceDB::test_instance_overrides_roundtrip`、
  `tests/test_db.py::TestInstanceDB::test_mood_numbers_are_not_persisted`。

### 13.10 UI 分层与「一处实现」原则（第四轮抽象审计结论，必守）

审计发现并已修正的四处重复，后续改动不得回退：

- **渲染壳必须继承 `ui/shell_base.py:PetShell`**：控件装配、四个交互信号
  （`pet_clicked / pat_requested / menu_requested / passthrough_changed`）、`tick()`
  （先 `flush_mood_events` 再 `widget.tick()` + `music_tick`）、`music_reaction()`、
  `close_shell()` 只在基类实现。`ui/desktop.py` 与 `ui/overlay.py` 只实现
  `_prepare()` / `_create_widget()`（overlay 额外允许覆盖 `close_shell`/`set_opacity`/
  `nativeEvent`/`_accepts`）。新增壳种照此继承，**不要**再复制一遍装配循环。
  回归防线：`tests/test_shell_interface.py`。
- **样式表文本住 `ui/qss.py`**：`nav_stylesheet / content_stylesheet / panel_stylesheet /
  bubble_colors` 是纯字符串生成，与 `theme.py`（只放配色数据与派生色计算）分开；
  消费方 `from .qss import …`，不要从 `theme.py` 再导一遍。
- **通用布局工具住 `ui/layout.py`**：`hint()` / `scroll()` / `vbox()` 被聊天框、
  全局设置、实例设置共用，不要再寄居在 `ui/sidebar.py` 里被反向 import。
- **菜单动作只有一份**：`app/tray.py:_add_pet_actions(menu, pet_id, *, include_remove=False)`
  同时供给托盘实例子菜单（`include_remove=True`）与宠物右键菜单；新增右键项改这里一处。
  回归防线：`tests/test_menu_actions.py`。

### 13.11 调试产物用完即删，禁止用 .gitignore 兜底（用户明确要求，必守）

用户原话（2026-11-16）：「你这补的规则治标不治本啊，以后调试完垃圾用完就删吧。」
补 ignore 规则等于承认「垃圾会一直躺在仓库里」，以后每次都要维护规则、还可能漏网。
所以纪律是**产出即清理**，不是**产出即忽略**。

- **调试产物不许留在仓库里**：诊断截图 `diag_*.png`、`evidence_*.png`、`probe_*.png`、
  `smoke_*.png`、抓屏输出 `diag_status_out.txt` / `live_out.txt` / `live_err.txt`、
  一次性脚本、临时 sqlite、`ka-am-pet.spec`、`build/`、`dist/`、`.userdata/`（源码兜底数据目录除外，
  见下）——用完当场删，不要「先留着，说不定还要看」。
  本仓库 2026-11-16 清理过一次：删掉 3 张诊断截图（3.4MB）、2 个输出 txt、6 个 `scripts/diag_*.py`、
  `diag_imgs.py`、`ka-am-pet.spec`，以及 54MB `build/` + 50MB `dist/`。
- **`.gitignore` 只放环境/构建产物**：`venv/`、`__pycache__/`、`dist/`、`build/`、`*.spec`、
  `.pytest_cache/`、`.idea/`、`wheelhouse/`、`.userdata/`。
  想加新规则前先自问：这条是「**本该被删掉的东西**」还是「**环境产物**」？
  前者去删文件，不要写规则；只有后者才配待在 `.gitignore` 里。
- **调试脚本要留就留得干净**：放 `scripts/` 的脚本必须在仓库外产生产物——
  截图写 `tempfile.gettempdir()`（参考 `scripts/click_popup_smoke.py`、
  `scripts/gui_smoke.py`），文件头用 docstring 说明用途；一次性的诊断脚本不要入库，跑完删掉。
- **提交前自检**：`git status --porcelain` 只允许出现本次预期改动的文件；
  一旦冒出未跟踪的 `*.png` / `*.txt` / `*.db` / `*.spec` / `*.log`，先删掉再谈提交，
  不要 `git add` 进索引、更不要加 ignore 规则掩盖。
