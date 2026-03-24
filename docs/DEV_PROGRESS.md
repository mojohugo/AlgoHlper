# 开发进度记录

更新时间：2026-03-24

## 本轮已完成

### 1. 仓库初始化
- 初始化了本地 Git 仓库。
- 建立了 Python 项目骨架：`pyproject.toml`、`src/`、`tests/`、`docs/`。

### 2. 核心领域模型
- 建好了 `ProblemSpec`、`ProjectRecord`、`ArtifactRecord`、`TaskRecord`、`DuelResult` 等 Pydantic 模型。
- 目前先用文件持久化，数据目录是 `.algohlper_data/`。

### 3. 题面解析
- 实现了规则驱动的 `ProblemSpec` 解析器。
- 支持抽取：标题、题目描述、输入格式、输出格式、约束、样例、问题类型猜测、特殊说明。
- 当前是启发式方案，方便后续接入 LLM 做结构化补全。

### 4. Starter 资产生成
- 实现了 starter 版本的：
  - `brute.cpp`
  - `gen.cpp`
  - `compare.py`
  - `README.md`
- 这些文件目前是模板，不是最终可直接对拍的真·参考解。

### 4.1 可插拔代码生成入口
- 新增 `template / openai / auto` 三种 provider。
- `auto` 会在检测到 `OPENAI_API_KEY` 时走 OpenAI，否则自动回退到模板生成器。
- 新增 API：`POST /api/projects/{project_id}/generate-artifacts`
- 新增 CLI：`algohlper generate`
- 目前 `openai provider` 已接好接口，但默认仍建议当作“带 fallback 的实验入口”。

### 4.2 生成后自检
- 新增生成资产自检服务：
  - `brute.cpp` 编译检查
  - `gen.cpp` 编译检查
  - `generator smoke test`
  - `brute` 样例回放（最多 3 个样例）
- 当前策略：
  - `openai provider` 默认执行自检，不通过就报错/回退
  - `template provider` 因为本身是占位模板，默认跳过自检并显式返回 skipped

### 4.3 OpenAI 自动回修
- `openai provider` 现在支持在首次生成失败后，携带以下上下文再请求一次模型：
  - 编译日志
  - generator smoke test 结果
  - brute 样例校验结果
  - 上一轮生成代码
- 当前默认回修 1 轮，且上限限制在 2 轮以内。

### 4.4 Codex 配置兼容
- 现在会兼容读取 `CODEX_API_KEY`。
- 现在会读取 `C:\Users\mojo_\.codex\config.toml` 中的：
  - `model`
  - `model_reasoning_effort`
  - `model_providers.<provider>.base_url`
  - `model_providers.<provider>.env_key`
- 这样本地已经配好的 Codex 环境，可以直接给项目复用。

### 6.1 异步任务骨架
- 新增进程内异步任务队列骨架（ThreadPoolExecutor）。
- 新增接口：
  - `POST /api/projects/{project_id}/parse-async`
  - `POST /api/projects/{project_id}/generate-artifacts-async`
  - `POST /api/projects/{project_id}/duel-async`
- 当前这是 MVP 级骨架，目标是先把同步 API 改成“发任务 + 查状态”的工作流。
- 这不是最终方案；后续应替换为 Redis + Celery/worker。

### 6.2 队列后端抽象
- 已把任务提交层抽成统一队列接口。
- 当前支持两种 backend：
  - `inprocess`
  - `celery`
- 当前行为：
  - 如果设置 `ALGOHLPER_TASK_QUEUE_BACKEND=celery` 且安装了 Celery，则走 Celery task
  - 否则自动回退到 `inprocess`
- 已增加：
  - `src/algohlper/services/task_queue.py`
  - `src/algohlper/services/job_runner.py`
  - `src/algohlper/worker/celery_app.py`
  - `src/algohlper/worker/tasks.py`

### 6.3 Windows Redis 本地联调
- 已支持通过以下环境变量直接拼 Redis URL：
  - `ALGOHLPER_REDIS_HOST`
  - `ALGOHLPER_REDIS_PORT`
  - `ALGOHLPER_REDIS_PASSWORD`
- 已新增 PowerShell 启动脚本：
  - `scripts/start_api.ps1`
  - `scripts/start_worker.ps1`
- Windows 下 worker 默认建议走 `solo` pool，适合作为本地开发模式。

### 7. 前端最小工作台
- 已新增 `apps/web`，采用 Next.js App Router 最小骨架。
- 当前已接通这些流程：
  - 项目列表与新建项目
  - 保存题面
  - 异步解析
  - 异步生成
  - 保存用户代码
  - 异步对拍
  - 任务轮询与日志展示
  - 产物代码标签页预览
  - 失败样例卡片
  - expected / actual 输出 diff 视图
- 已新增 `scripts/start_web.ps1`，用于本地 Windows 启动前端。

### 5. 本地对拍内核
- 实现了 C++ 编译与执行封装，基于本机 `g++`。
- 实现了标准对拍循环：`gen -> brute -> user -> compare`。
- 能返回首个失败样例，包括 seed、mode、size、输入、期望输出、实际输出、stderr。
- 当前内核是本地 `subprocess` 方案，尚未接入容器沙箱。

### 6. FastAPI API
已提供接口：
- `GET /healthz`
- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/problem-text`
- `POST /api/projects/{project_id}/parse`
- `GET /api/projects/{project_id}/problem-spec`
- `PUT /api/projects/{project_id}/problem-spec`
- `POST /api/projects/{project_id}/generate-artifacts`
- `POST /api/projects/{project_id}/generate-starter-artifacts`
- `POST /api/projects/{project_id}/artifacts`
- `GET /api/projects/{project_id}/artifacts`
- `POST /api/projects/{project_id}/duel`
- `GET /api/projects/{project_id}/duel-result`
- `GET /api/tasks/{task_id}`

### 7. CLI
已提供命令：
- `algohlper parse`
- `algohlper starter`
- `algohlper generate`
- `algohlper duel`

### 8. 测试
- 写了题面解析测试。
- 写了 API 烟雾测试。
- 写了对拍测试，能稳定发现错误程序的反例。
- 写了资产自检测试，覆盖编译成功/失败路径。
- 写了 OpenAI 自动回修测试，覆盖“首次生成失败、第二次修复成功”的路径。
- 写了配置兼容测试，覆盖 `CODEX_API_KEY` / `.codex/config.toml`。
- 写了异步 API 测试，覆盖任务提交和轮询完成。
- 写了队列 backend 测试，覆盖 Celery 不可用时自动回退到 in-process。
- 写了 Redis URL 组装测试，覆盖 Windows 本地 Redis 密码场景。
- 跑通了前端 `npm run build`，确认 Next.js 最小工作台可以构建。

## 当前明确未完成

- Celery/Redis 目前还是“可切换骨架”，还没补 docker-compose、真正 Redis 联调、任务重试策略和 worker 运行文档细节。
- 前端目前还是单页最小工作台，尚未拆组件状态层、Monaco 编辑器、Diff Viewer、SSE 日志流。
- `openai provider` 已有基础自检和单轮自动回修，但还没有做更严格的 schema 约束、样例不足时的补测策略、以及多轮稳定性治理。
- 没有 PostgreSQL / Redis / Celery。
- 没有 Docker / gVisor Runner。
- 没有前端页面。
- 没有反例最小化。
- 没有用户系统和多租户。

## 建议下一个模型接手时先读

1. `algorithm_duipai_agent_dev_doc.md`
2. `README.md`
3. `docs/DEV_PROGRESS.md`
4. `src/algohlper/api/app.py`
5. `src/algohlper/services/duel.py`
6. `src/algohlper/services/problem_parser.py`

## 下一步推荐顺序

1. 先强化 `openai provider`：结构化输出校验、编译失败自动修复、样例自测。
2. 再把 `POST /parse` 和 `POST /duel` 改成异步任务。
3. 再拆独立 runner，接容器隔离。
4. 最后补前端工作台。
