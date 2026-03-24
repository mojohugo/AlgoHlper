# AlgoHlper

基于 `algorithm_duipai_agent_dev_doc.md` 启动的第一版代码骨架，当前重点是把 **题面解析 + 本地 C++ 对拍闭环 + FastAPI 接口** 先跑起来。

## 当前已实现

- `ProblemSpec` 规则解析器：把 Markdown / text 题面提取成结构化 JSON。
- 本地 JSON 持久化：项目、任务、代码资产、对拍结果都会落到 `.algohlper_data/`。
- Starter 资产生成：自动生成 `brute.cpp`、`gen.cpp`、`compare.py`、`README.md` 模板，便于后续接 LLM 真正生成代码。
- 可插拔代码生成器：新增 `template / openai / auto` 三种 provider 入口。未配置 OpenAI 时，`auto` 会自动回退到模板生成器。
- 生成后自检：对 `openai provider` 生成的 `brute.cpp` / `gen.cpp` 会先做编译检查、generator smoke test、样例回放，再决定是否落库。
- 自动回修：如果 `openai provider` 首次生成未通过自检，会带着编译日志和样例失败信息自动回修 1 轮（可调）。
- Codex 环境兼容：现在会自动兼容 `CODEX_API_KEY`，并读取 `C:\Users\mojo_\.codex\config.toml` 里的 `base_url / model / reasoning` 配置。
- 异步任务骨架：新增 `parse-async / generate-artifacts-async / duel-async` 三个接口，先用进程内队列跑任务。
- 队列后端抽象：现在支持 `inprocess / celery` 两种后端入口；未安装 Celery 或未配置时会回退到 `inprocess`。
- 最小前端工作台：新增 `apps/web`，可直接操作项目、题面、异步生成、用户代码上传与异步对拍。
- 前端结果视图：新增产物标签页、失败样例卡片、expected/actual 输出 diff，便于直接看首个反例。
- 前端视觉重构：重新整理了侧栏、指标卡片、编辑区和日志区布局，当前页面已经更接近工作台形态。
- 前端 Monaco 工作台：题面、用户代码、产物、结构化题面、日志都已切到 Monaco 编辑器，并支持一键复制。
- 前端结构化题面表单编辑：可直接修改标题、描述、输入输出、约束、样例与备注后保存。
- 前端快速运行：支持把对拍失败输入一键回填到“快速运行”面板，直接运行当前 `user_solution` 看 stdout/stderr。
- 前端分区式工作台：已按工作流拆成 `概览 / 编辑 / 生成资产 / 对拍运行` 四个分区，减少所有功能堆在一页导致的操作负担。
- 前端状态文案与徽标优化：`counterexample_found` 这类后台状态已转成人类可读文案，并修复长状态挤出卡片的问题。
- 前端中文化继续收口：项目摘要、运行环境、产物标签、快测输出、对拍结果等主要可见文案已统一改成中文表述。
- 前端冗余信息收缩：概览页移除了重复的运行环境摘要和过多状态卡片，项目列表也去掉了噪音更大的项目 ID 展示。
- C++ 对拍引擎：调用本机 `g++` 编译 `brute.cpp` / `gen.cpp` / `main.cpp`，执行多轮随机对拍并返回首个失败样例。
- FastAPI 接口：项目、题面上传、解析、资产写入、starter 资产生成、对拍、快速运行、任务查询。
- CLI：支持 `parse`、`starter`、`generate`、`duel` 四个命令。
- Pytest 覆盖：题面解析、API 烟雾测试、对拍发现反例。

## 当前未实现

- 真实 LLM 驱动的 brute/gen 自动生成
- PostgreSQL / Redis / Celery
- 独立 Runner Service / Docker / gVisor 沙箱
- 反例最小化

## 本地启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
# 如果你要启用 OpenAI 代码生成 provider：
# python -m pip install -e .[dev,openai]
# 如果你要启用 Celery / Redis 队列：
# python -m pip install -e .[dev,queue]
uvicorn algohlper.api.app:app --app-dir src --reload
```

如果你本机已经在 Codex 里配置了：

- 环境变量：`CODEX_API_KEY`
- 配置文件：`C:\Users\mojo_\.codex\config.toml`

那现在 `AlgoHlper` 会直接复用这套配置，不需要再单独补 `OPENAI_API_KEY`。

## 队列后端

默认：

```powershell
$env:ALGOHLPER_TASK_QUEUE_BACKEND="inprocess"
```

如果你准备切到 Celery：

```powershell
$env:ALGOHLPER_TASK_QUEUE_BACKEND="celery"
$env:ALGOHLPER_REDIS_HOST="127.0.0.1"
$env:ALGOHLPER_REDIS_PORT="6379"
$env:ALGOHLPER_REDIS_PASSWORD="123456"
```

Worker 启动命令：

```powershell
celery -A algohlper.worker.tasks.celery_app worker --loglevel=info --pool=solo
```

或者直接用仓库里给你的 PowerShell 脚本：

```powershell
.\scripts\start_worker.ps1 -RedisPassword 123456
.\scripts\start_api.ps1 -RedisPassword 123456
```

说明：
- 你的环境是 Windows，所以 Celery worker 默认建议用 `--pool=solo`。Celery 官方文档说明 Windows 不再正式支持，`solo` 池仍可用，适合本地开发。
- 官方文档：  
  - Celery workers on Windows: https://docs.celeryq.dev/en/stable/faq.html#does-celery-support-windows  
  - Celery Redis broker: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html

打开：<http://127.0.0.1:8000/docs>

## 前端工作台

前端目录：

```text
apps/web
```

安装依赖：

```powershell
cd .\apps\web
npm install
```

启动前端：

```powershell
..\..\scripts\start_web.ps1
```

或手动指定 API 地址：

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev -- --port 3000
```

前端默认地址：

```text
http://127.0.0.1:3000
```

你现在还能直接在前端里：

- 在 `概览` 里看最近任务、环境、最近对拍结果
- 在 `编辑` 里只处理题面、用户代码和快速运行
- 在 `生成资产` 里只处理生成参数、产物预览和结构化题面
- 在 `对拍运行` 里只处理对拍参数、日志和结果
- 发起解析 / 生成 / 对拍后自动切到对应分区，直接看当前任务和结果
- 直接用中文查看项目摘要、队列状态、标准输出 / 标准错误、期望输出 / 实际输出
- 编辑结构化题面
- 把对拍失败输入回填到快速运行面板
- 用当前编辑器里的 `user_solution` 跑单组输入
- 直接查看 stdout / stderr / 编译日志

## CLI 示例

### 解析题面

```powershell
algohlper parse .\problem.md --format markdown --output .\problem_spec.json
```

### 生成 starter 资产

```powershell
algohlper starter .\problem.md .\out --format markdown
```

### 按 provider 生成资产

```powershell
algohlper generate .\problem.md .\out --provider auto
```

如果你要显式控制回修轮数：

```powershell
algohlper generate .\problem.md .\out --provider openai --repair-rounds 1
```

生成目录里还会附带：

- `problem_spec.json`
- `generation_meta.json`（记录 provider、warnings、自检结果）

### 本地对拍

```powershell
algohlper duel --brute .\out\brute.cpp --generator .\out\gen.cpp --user .\main.cpp --rounds 200
```

## API 主流程

1. `POST /api/projects`
2. `POST /api/projects/{project_id}/problem-text`
3. `POST /api/projects/{project_id}/parse`
4. `POST /api/projects/{project_id}/generate-artifacts`
5. `POST /api/projects/{project_id}/generate-artifacts-async`
6. `POST /api/projects/{project_id}/artifacts` 覆盖 `brute` / `generator` / `user_solution`
7. `POST /api/projects/{project_id}/duel`
8. `POST /api/projects/{project_id}/duel-async`
9. `POST /api/projects/{project_id}/run-user`
10. `GET /api/tasks/{task_id}` 或 `GET /api/projects/{project_id}/duel-result`

## 推荐下一个开发步骤

1. 把 `openai provider` 做成更严格的结构化输出和多轮修复。
2. 把同步任务改成 Redis + Celery。
3. 把本地 `subprocess` 执行下沉为独立 Runner 服务。
4. 继续把前端工作台拆成更细的组件 / 独立页面，减少 `workbench.tsx` 体积。
