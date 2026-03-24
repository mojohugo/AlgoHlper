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

## 当前明确未完成

- `openai provider` 虽已接入，但还没有做多轮 repair、结构化严格校验、编译后自动回修。
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
