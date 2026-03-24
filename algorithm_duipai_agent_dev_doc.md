# 自动生成算法题对拍 Agent 开发文档

## 1. 项目目标

构建一个面向算法竞赛/刷题场景的智能对拍系统（以下简称 **DuelAgent**），支持用户将题面（纯文本、Markdown、LaTeX）直接提交给系统，系统自动：

1. 解析题意与输入输出格式；
2. 生成**暴力解 / 参考解**；
3. 生成**随机数据生成器**；
4. 将用户提交代码与参考解进行批量对拍；
5. 自动发现首个错误样例并回显；
6. 提供完整 Web 前端、后端 API、任务队列、代码执行沙箱与日志链路；
7. 第一阶段优先支持 **C++**，后续可扩展 Java / Python / Rust / Go 等语言。

这是一个“**LLM + Sandboxed Judge + 产品化工作流**”系统，而不是单纯的在线 IDE。系统核心价值在于：

- **把题面直接转成可对拍资产**（brute / generator / validator / runner）；
- **自动化发现用户代码错误样例**；
- **对问题可解释**：生成原因、风险点、失败日志、最小反例都能展示；
- **可演进**：从 C++ 单语言逐步扩到多语言、多模型、多沙箱策略。

---

## 2. 产品定位与核心用户

### 2.1 用户画像

1. **算法竞赛用户**：OI / ICPC / Codeforces / LeetCode 高强度练习者；
2. **算法培训讲师/助教**：需要快速构造题目、校验标程与错误程序；
3. **题库平台研发**：可复用对拍链路做出题验题、回归测试；
4. **个人开发者**：希望用更低门槛完成“题面 → 暴力 → 对拍 → 反例”。

### 2.2 核心场景

#### 场景 A：用户只有题面
- 粘贴 Markdown / LaTeX 题面；
- 系统分析约束和数据范围；
- 自动给出 `brute.cpp`、`gen.cpp`、可选 `validator.cpp`；
- 用户再上传自己的 `main.cpp`，开始对拍。

#### 场景 B：用户已有代码但 WA 原因不明
- 用户上传题面 + 自己代码；
- 系统自动生成参考暴力解；
- 执行多轮随机数据测试；
- 返回首个失败样例、期望输出、实际输出、复现命令。

#### 场景 C：用户想审查生成质量
- 用户查看“题意结构化提取结果”；
- 用户可手动编辑输入格式、约束、数据生成策略；
- 再触发重新生成。

---

## 3. 成功标准（MVP / V1 / V2）

### 3.1 MVP（4~6 周）

支持：
- 题面输入：text / markdown / latex；
- 语言：C++；
- 自动生成：
  - brute.cpp
  - gen.cpp
  - compare.py（或内置 diff 逻辑）
- 用户上传 `main.cpp`；
- 批量对拍，返回首个错误样例；
- 前端展示任务状态、日志、代码预览、错误样例；
- 安全沙箱执行；
- 单机部署可用。

### 3.2 V1（8~12 周）

新增：
- 多轮 agent 纠错（生成失败自动修复 1~2 次）；
- validator 生成；
- 最小化反例（counterexample minimization）；
- 项目保存与历史任务；
- 用户可手动编辑生成器模板；
- 多租户/账号系统；
- 可观测性、告警、管理后台。

### 3.3 V2

新增：
- 多语言（Python / Java / Rust / Go）；
- 支持交互题 / 特判题；
- 模型切换（高质量 / 低成本）；
- 团队协作与共享项目；
- 批量题目处理；
- 题库平台 API 集成。

---

## 4. 技术栈选型（最终推荐）

本项目最优先考虑以下四件事：

1. **Agent 编排与 Python 生态兼容性**；
2. **前端交互与代码编辑体验**；
3. **不可信代码执行的安全性**；
4. **异步任务与高并发对拍吞吐**。

### 4.1 前端：Next.js + TypeScript + Tailwind + shadcn/ui + Monaco Editor

**推荐栈：**
- **Next.js (App Router)**
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui**
- **Monaco Editor**
- **React Query / TanStack Query**
- **Zustand**（轻量状态管理）

**选择理由：**
- Next.js App Router 适合做现代全栈前端、SSR/流式渲染、后台管理页面与 API 网关层；
- TypeScript 保证复杂表单、任务状态和代码编辑器状态安全；
- Tailwind + shadcn/ui 开发速度快、UI 一致性高；
- Monaco 是 VS Code 同源编辑器，适合代码输入、diff、语法高亮与只读日志展示；
- React Query 非常适合轮询任务状态、管理缓存和失败重试。

**为什么不是 Vue/Nuxt：**
- 也能做，但在“代码编辑器 + BFF + 复杂产品台”这类工程场景，Next.js 生态与团队招聘面更优。

### 4.2 后端 API：FastAPI + Pydantic + SQLAlchemy

**推荐栈：**
- **FastAPI**
- **Pydantic v2**
- **SQLAlchemy 2.x**
- **Alembic**
- **Uvicorn / Gunicorn**

**选择理由：**
- FastAPI 对异步 I/O、文件上传、任务发起、WebSocket/SSE 支持友好；
- 与 Python LLM/Agent 生态天然兼容；
- Pydantic 非常适合定义“题面解析结果”“生成任务”“沙箱执行结果”等结构化模型；
- 文档自动生成快，前后端联调成本低。

**为什么不是 NestJS / Spring Boot：**
- 这类系统最重的智能逻辑、代码编排、编译运行 orchestration 都更贴近 Python 生态；
- FastAPI 能减少“模型调用 + 任务编排 + 沙箱调度”跨语言摩擦。

### 4.3 Agent/任务编排：Python Worker + Redis Queue（Celery 或 RQ）

**最终建议：**
- MVP 使用 **Celery + Redis**；
- 若未来任务类型更复杂，可演进为 **Temporal** 或 **自定义事件流任务系统**。

**原因：**
- 对拍任务是典型的长任务、异步任务、可重试任务；
- 代码编译、样例生成、批量运行绝不能阻塞 API 进程；
- Celery 成熟、生态大、部署成本低；
- Redis 可以同时承担缓存、队列 Broker、短期运行状态存储。

**注意：**
- FastAPI 自带 BackgroundTasks 仅适合轻量后台任务，不适合长时间编译/运行/多轮 agent 修复任务。

### 4.4 数据库：PostgreSQL

**推荐：**
- **PostgreSQL 16+**

**原因：**
- 结构化数据（用户、项目、任务、运行结果）和半结构化数据（题目解析 JSON、模型中间结果）都能很好支持；
- `jsonb` 很适合存储题面抽取结果与 agent trace；
- 后续可利用全文检索做项目搜索、日志搜索。

### 4.5 对象存储：S3 / MinIO

用于存储：
- 用户原始题面文件；
- 生成代码资产；
- 失败样例；
- 编译日志、运行日志；
- 下载包（zip）。

**开发环境：** MinIO

**生产环境：** AWS S3 / Cloudflare R2 / 阿里云 OSS（三选一，接口层抽象统一）

### 4.6 代码执行沙箱：Docker Rootless + gVisor（首选）

**最终推荐：**
- **第一层**：独立 Runner Service
- **第二层**：**Rootless Docker**
- **第三层**：**gVisor runsc** 运行时
- **补充限制**：CPU / Memory / PIDs / no-network / read-only FS / seccomp / timeout

**为什么这样选：**
- 对拍系统会执行**用户上传的非可信代码**，安全是生命线；
- Rootless 可以降低容器与 daemon 的宿主机风险面；
- gVisor 为容器提供更强隔离层，适合“执行不可信工作负载”；
- 这套方案比“直接宿主机编译运行”安全得多，也比手写轻量沙箱更稳。

**为什么不建议 MVP 直接裸用 nsjail：**
- nsjail 很强，也很适合 judge 场景；
- 但如果团队更熟悉容器化交付与 CI/CD，Docker + gVisor 的工程落地与维护成本更低；
- 后续可将 nsjail 作为“极致性能 runner”增量方案接入。

### 4.7 解析与渲染：Pandoc + Markdown AST + KaTeX

**推荐：**
- 文本预处理：Python 自定义 parser
- 文档格式归一：**Pandoc**
- 数学公式前端渲染：**KaTeX**

**理由：**
- 题面来源可能是纯文本、Markdown、LaTeX 混合内容；
- Pandoc 能较好地完成格式归一与结构转换；
- KaTeX 渲染速度快，适合题面预览与结构化校对页面。

### 4.8 测试体系：Pytest + Playwright

- 后端：**Pytest**
- 前端 E2E：**Playwright**
- Runner 集成测试：自建题库回归集

### 4.9 可观测性

- 日志：**structlog / Python logging JSON**
- 指标：**Prometheus**
- 仪表盘：**Grafana**
- 错误追踪：**Sentry**
- 链路追踪：**OpenTelemetry**

---

## 5. 总体架构设计

```text
[Web Frontend / Next.js]
        |
        v
[API Gateway / FastAPI]
        |
        +----------------------+
        |                      |
        v                      v
[PostgreSQL]              [Redis]
        |                      |
        |                      v
        |                 [Task Queue]
        |                      |
        |                      v
        |              [Agent Worker / Python]
        |                      |
        |              1. parse problem
        |              2. generate brute/gen
        |              3. compile assets
        |              4. run duel
        |              5. minimize case
        |                      |
        v                      v
   [Object Storage]      [Runner Service]
                                 |
                                 v
                    [Rootless Docker + gVisor Sandbox]
```

### 5.1 架构分层

#### A. Presentation Layer（展示层）
- 题面输入页
- 工程工作台
- 代码编辑页
- 对拍结果页
- 历史记录页

#### B. API Layer（接口层）
- 用户认证
- 项目管理
- 文件上传
- 任务发起
- 任务状态查询
- 日志流接口

#### C. Agent Layer（智能层）
- 题面解析
- 约束抽取
- 代码生成
- 自检修复
- 风险评分

#### D. Execution Layer（执行层）
- 编译
- 随机数据生成
- 运行比对
- 反例最小化
- 结果归档

#### E. Infrastructure Layer（基础设施层）
- 队列
- 数据库
- 存储
- 监控
- 安全隔离

---

## 6. 核心能力拆解

### 6.1 题面解析模块

输入：
- plain text
- markdown
- latex
- 可选附件（图片后续支持 OCR，不建议 MVP 做）

输出（结构化 ProblemSpec）：

```json
{
  "title": "string",
  "statement": "string",
  "input_format": "string",
  "output_format": "string",
  "constraints": {
    "n": "1 <= n <= 2e5",
    "ai": "-1e9 <= ai <= 1e9"
  },
  "samples": [
    {
      "input": "...",
      "output": "..."
    }
  ],
  "problem_type_guess": ["array", "greedy", "graph"],
  "special_notes": ["multiple testcases", "1-indexed"]
}
```

#### 解析策略

采用“两阶段解析”：

1. **规则提取**
   - 标题、样例、输入输出标题、约束关键词；
   - 正则 + Markdown AST + LaTeX 块识别；
2. **LLM 结构化补全**
   - 将规则提取结果作为上下文；
   - 让模型输出严格 JSON Schema；
   - 对结果做 schema 校验。

#### 关键原则

- **永远不要直接用原题面让模型“一步到位写代码”**；
- 必须先抽取成 ProblemSpec，中间态可视化给用户确认；
- 这样能显著提高生成代码可控性与可修复性。

### 6.2 暴力解生成模块

目标：生成用于对拍的正确性优先参考解，而非最优解。

#### 生成要求
- 优先正确性，不优先复杂度；
- 适用于小数据；
- 必须显式写清：
  - 时间复杂度
  - 小数据适用范围
  - 为什么理论上可作为 reference

#### 提示词约束建议

要求模型输出：
1. 问题理解；
2. 小规模版本思路；
3. 暴力 C++ 代码；
4. 自测说明；
5. 风险点（样例覆盖不足、边界未证明等）。

#### 质量门禁

生成后自动做：
- 编译检查；
- 样例运行；
- 静态扫描（禁止网络、文件系统越权、fork bomb 形态代码）；
- 二轮自修复（如编译失败）。

### 6.3 随机数据生成器模块

目标：生成 `gen.cpp`，用于对拍。

#### 生成策略
- 支持按约束随机；
- 支持边界数据；
- 支持偏置数据：
  - 全相等
  - 严格递增
  - 严格递减
  - 极端值
  - 稀疏/稠密图
  - 多 testcase

#### 生成器输出形式

建议统一生成命令行参数风格：

```bash
./gen seed mode size
```

例如：
- `seed`: 随机种子
- `mode`: random / edge / adversarial / small
- `size`: 控制规模

#### 最佳实践
- 生成器必须可复现（固定种子）；
- 所有失败样例都能导出为独立输入文件；
- 后续最小化反例可以以此为基础进行 shrinking。

### 6.4 对拍执行模块

#### 工作流

1. 编译 `brute.cpp`
2. 编译 `gen.cpp`
3. 编译用户 `main.cpp`
4. 批量循环：
   - 调用 `gen` 生成输入
   - 分别喂给 `brute` 与 `main`
   - 比较输出
5. 一旦出现差异：
   - 保存输入
   - 保存两份输出
   - 保存退出码与 stderr
   - 触发反例最小化
6. 返回首个失败样例

#### 比较策略
- 默认：trim trailing spaces + final newline tolerant；
- 可切换：strict compare；
- 后续：支持 special judge。

### 6.5 反例最小化模块

对拍找出的错误样例，通常还不够“可读”。

#### 目标
将复杂随机输入收缩为更小、更具解释性的失败样例。

#### 实现思路
- 数值 shrinking：二分缩小数值范围；
- 数组 shrinking：删除元素、保留子段；
- 图 shrinking：删边、删点；
- 多 testcase shrinking：减少组数；
- 每次 shrink 后重新跑两份程序验证差异是否仍存在。

#### 价值
- 极大提升用户体验；
- 有利于 LLM 进一步解释“为什么这份代码错”。

---

## 7. Agent 设计

### 7.1 为什么不用单轮“大提示词”

单轮从题面直接生成 brute / gen / validator 很容易：
- 漏掉约束；
- 错读输入格式；
- 样例能过但本质错误；
- 编译失败时无恢复能力。

所以应该采用**多阶段 Agent Pipeline**。

### 7.2 推荐 Agent Pipeline

```text
Step 1. NormalizeProblem
Step 2. ExtractProblemSpec
Step 3. GenerateBrute
Step 4. GenerateGenerator
Step 5. CompileAndSelfTest
Step 6. CritiqueAndRepair (optional, max 2 rounds)
Step 7. PackageArtifacts
Step 8. DuelAgainstUserCode
Step 9. MinimizeCounterexample
Step 10. ExplainFailure
```

### 7.3 各步骤说明

#### Step 1 NormalizeProblem
- 把 markdown / latex / plain text 统一成内部文本格式；
- 保留 code block、公式块、样例块。

#### Step 2 ExtractProblemSpec
- 输出结构化 JSON；
- 对关键字段置信度打分；
- 低置信度字段前端高亮提示用户确认。

#### Step 3 GenerateBrute
- 根据 ProblemSpec 生成小规模正确性优先参考解。

#### Step 4 GenerateGenerator
- 根据 ProblemSpec + brute 生成数据生成器。

#### Step 5 CompileAndSelfTest
- 编译所有资产；
- 用样例和少量 smoke tests 验证；
- 失败则打回上游。

#### Step 6 CritiqueAndRepair
- 读取编译器错误、运行错误、样例不一致；
- 让模型做有限轮修复；
- 超过 2 轮直接报错给用户，不无穷重试。

#### Step 7 PackageArtifacts
- 保存 `brute.cpp`、`gen.cpp`、`meta.json`、`trace.json`。

#### Step 8 DuelAgainstUserCode
- 用户上传后开始真实对拍。

#### Step 9 MinimizeCounterexample
- 生成更小失败样例。

#### Step 10 ExplainFailure
- 使用失败输入、两份输出、用户代码片段，生成解释文本。

### 7.4 模型调用策略

建议分级：

- **高质量模型**：用于 ProblemSpec 抽取、brute 生成；
- **中成本模型**：用于 generator、repair、explain；
- **规则引擎**：用于 compare、compile、retry policy。

### 7.5 模型输出约束

每一步都要：
- 指定输出 schema；
- 强制 fenced code block；
- 严格限制语言；
- 对代码提取后单独存文件；
- 失败时带错误日志重试，不让模型“盲修”。

---

## 8. 前端设计

### 8.1 页面结构

#### 1）首页 / 工作台
- 新建项目
- 最近项目
- 导入题面

#### 2）题面解析页
- 左侧：原题面输入
- 右侧：结构化解析结果
- 支持用户手动修正输入格式、约束、样例

#### 3）资产生成页
- 展示生成状态：`Parsing -> Generating -> Compiling -> Self-testing`
- 可查看 `brute.cpp`、`gen.cpp`
- 支持“重新生成”

#### 4）对拍页
- 上传 / 粘贴用户代码
- 设置对拍轮数、时间限制、生成模式
- 展示实时日志流

#### 5）结果页
- 首个错误样例
- 用户输出 / brute 输出 diff
- 最小化失败样例
- 失败原因解释
- 下载复现包

### 8.2 关键组件

- `ProblemInputPanel`
- `ProblemPreviewPanel`
- `ProblemSpecEditor`
- `CodeArtifactTabs`
- `UserCodeEditor`
- `TaskStatusTimeline`
- `LiveLogsPanel`
- `CounterexampleCard`
- `OutputDiffViewer`

### 8.3 交互细节

#### 任务状态
状态机建议：
- `draft`
- `parsing`
- `generating`
- `self_testing`
- `ready`
- `dueling`
- `failed`
- `counterexample_found`
- `completed`

#### 实时更新
推荐：
- MVP：轮询 `GET /tasks/{id}`
- V1：SSE（Server-Sent Events）推送任务日志
- V2：WebSocket

### 8.4 为什么不用传统表单式后台

因为这是一个“工程工作台型产品”，用户要频繁：
- 输入题面；
- 编辑 JSON 结构；
- 查看多份代码；
- 看日志流；
- 看 diff；
- 复跑任务。

所以前端必须像一个轻量 IDE，而不是普通 CRUD 后台。

---

## 9. 后端 API 设计

以下为推荐 REST API 设计。

### 9.1 项目与题面

#### 创建项目
`POST /api/projects`

```json
{
  "name": "CF xxxx duel test"
}
```

#### 上传题面文本
`POST /api/projects/{project_id}/problem-text`

```json
{
  "content": "...markdown/latex/text...",
  "format": "markdown"
}
```

#### 获取题面结构化结果
`GET /api/projects/{project_id}/problem-spec`

#### 更新题面结构化结果
`PUT /api/projects/{project_id}/problem-spec`

### 9.2 资产生成

#### 发起生成任务
`POST /api/projects/{project_id}/generate`

```json
{
  "language": "cpp",
  "assets": ["brute", "generator"],
  "repair_rounds": 2
}
```

#### 获取生成结果
`GET /api/projects/{project_id}/artifacts`

### 9.3 用户代码与对拍

#### 上传用户代码
`POST /api/projects/{project_id}/user-solution`

```json
{
  "language": "cpp",
  "code": "#include <bits/stdc++.h>..."
}
```

#### 发起对拍
`POST /api/projects/{project_id}/duel`

```json
{
  "rounds": 500,
  "time_limit_ms": 1000,
  "memory_limit_mb": 256,
  "generator_mode": ["random", "edge", "small"],
  "stop_on_first_fail": true,
  "minimize_counterexample": true
}
```

#### 查询对拍结果
`GET /api/projects/{project_id}/duel-result`

### 9.4 任务接口

#### 获取任务详情
`GET /api/tasks/{task_id}`

#### 获取任务日志
`GET /api/tasks/{task_id}/logs`

#### SSE 日志流
`GET /api/tasks/{task_id}/events`

---

## 10. 数据模型设计

### 10.1 表结构建议

#### users
- id
- email
- name
- created_at

#### projects
- id
- user_id
- name
- status
- created_at
- updated_at

#### problems
- id
- project_id
- raw_content
- raw_format
- normalized_content
- problem_spec_jsonb
- parse_confidence_jsonb
- created_at

#### artifacts
- id
- project_id
- type (`brute`, `generator`, `validator`, `user_solution`)
- language
- code_text
- compile_status
- compile_log
- storage_key
- created_at

#### tasks
- id
- project_id
- type (`parse`, `generate`, `duel`, `minimize`)
- status
- progress
- payload_jsonb
- result_jsonb
- error_jsonb
- started_at
- finished_at

#### duel_runs
- id
- project_id
- task_id
- rounds_requested
- rounds_completed
- fail_found
- first_fail_input_key
- expected_output_key
- actual_output_key
- stderr_key
- created_at

#### execution_logs
- id
- task_id
- level
- message
- detail_jsonb
- created_at

---

## 11. Runner 与沙箱设计

### 11.1 核心原则

用户代码与模型生成代码都必须视为“**不可信可执行物**”。

### 11.2 Runner 职责

Runner Service 独立部署，职责：
- 接收编译/运行请求；
- 准备临时工作目录；
- 注入代码文件；
- 在隔离环境中编译；
- 运行程序并采集 stdout/stderr/exit code/time/memory；
- 回传结果；
- 清理环境。

### 11.3 容器限制建议

每次执行都要限制：
- CPU quota
- memory
- process count
- file size
- wall clock timeout
- no outbound network
- read-only root filesystem
- tmpfs working dir
- non-root user

### 11.4 目录布局

```text
/work
  /input.txt
  /main.cpp
  /brute.cpp
  /gen.cpp
  /bin/
  /out/
```

### 11.5 C++ 编译建议

编译命令建议：

```bash
g++ -O2 -std=c++17 -pipe -static -s main.cpp -o main
```

注意：
- 某些环境 `-static` 体积大且兼容性一般，可在容器镜像内评估；
- 如果 runner 环境有兼容问题，改为 `-O2 -std=c++17 -pipe`；
- 后续可支持 C++20。

### 11.6 执行结果结构

```json
{
  "exit_code": 0,
  "stdout": "...",
  "stderr": "...",
  "time_ms": 12,
  "memory_kb": 3240,
  "timed_out": false,
  "oom": false
}
```

### 11.7 为什么 Runner 必须独立成服务

不要把编译与运行逻辑塞进 API 进程或 Agent Worker 内：
- 更危险；
- 更难做资源隔离；
- 更难横向扩容；
- 日后多语言镜像管理会混乱。

独立 Runner 才方便：
- 单独限权；
- 单独扩容；
- 单独监控；
- 单独做镜像版本治理。

---

## 12. 对拍策略设计

### 12.1 基础对拍循环

```text
for seed in seeds:
  input = gen(seed, mode, size)
  out_brute = brute(input)
  out_user = user(input)
  if compare(out_brute, out_user) == false:
      save_case()
      break
```

### 12.2 种子策略

建议混合：
- 顺序种子：1..N
- 时间种子：提升随机性
- 特殊种子池：固定保留一些容易炸边界的种子

### 12.3 模式策略

每轮可从以下模式抽样：
- `small_random`
- `edge_small`
- `degenerate`
- `adversarial_guess`
- `sample_like`

### 12.4 规模渐增

不要上来就打最大；推荐：
- 先 50 轮 very small
- 再 200 轮 small
- 再 250 轮 medium

原因：
- brute 解通常只适合小规模；
- 先快速找低成本反例效率更高。

### 12.5 对拍终止条件

- 找到首个失败样例；
- 达到最大轮数；
- 某方程序 RE/TLE；
- 用户主动停止。

---

## 13. 代码生成质量控制

### 13.1 生成物分类

系统至少输出：
- `brute.cpp`
- `gen.cpp`
- `meta.json`
- `README.md`（解释如何本地复现）

V1 可选：
- `validator.cpp`
- `checker.cpp`

### 13.2 自检规则

#### 编译期
- 必须能编译；
- 编译 warning 不作为失败，但应记录。

#### 运行期
- 样例必须通过；
- 生成器必须能生成合法输入；
- brute 在 very small 范围内必须可运行。

#### 逻辑期
- 检查生成器输出是否符合输入格式；
- 检查多个样例是否有基本多样性；
- 检查是否出现明显未定义行为迹象。

### 13.3 Repair 策略

出现以下情况允许自动修复：
- 编译错误
- 头文件遗漏
- 输入格式读错
- 样例没过

以下情况不建议自动多轮修复超过 2 次：
- 题意误读严重
- 生成器结构完全错误
- brute 复杂度和适用范围不明确

---

## 14. 安全设计

### 14.1 威胁模型

用户可能上传：
- 恶意代码；
- fork bomb；
- 死循环；
- 超大输出；
- 文件系统探测；
- 宿主机逃逸尝试；
- 利用编译器/运行时漏洞攻击。

### 14.2 必要措施

#### 基础隔离
- Rootless Docker
- gVisor
- no network
- read-only rootfs
- tmpfs workdir
- UID/GID 隔离

#### 资源限制
- CPU time
- wall time
- memory
- output size
- process count

#### 输入输出限制
- 单次输入文件大小限制
- 单次 stdout/stderr 截断
- 单任务总日志上限

#### 文件系统策略
- 禁止挂载宿主敏感目录
- 容器只挂临时目录
- 运行结束立即销毁

### 14.3 敏感能力禁用
- 禁网
- 禁特权容器
- 禁 docker socket 挂载
- 禁共享宿主 PID namespace
- 禁 host network

### 14.4 审计
- 每次执行记录：
  - 谁发起
  - 哪个项目
  - 使用了哪个镜像
  - 编译命令
  - 运行限制
  - 退出原因

---

## 15. 可观测性与运维

### 15.1 关键指标

#### API 层
- QPS
- P95/P99 latency
- 错误率

#### Agent 层
- 题面解析成功率
- 代码生成成功率
- 自动修复成功率
- 任务平均耗时

#### Runner 层
- 编译成功率
- 对拍平均轮数
- 失败样例发现率
- TLE/RE/OOM 比例
- Runner 实例利用率

### 15.2 告警建议

- 任务积压超过阈值
- Runner 无可用实例
- 连续生成失败率升高
- 沙箱异常退出率异常
- Redis/Postgres 连接异常

### 15.3 日志字段建议

```json
{
  "trace_id": "...",
  "task_id": "...",
  "project_id": "...",
  "stage": "generate_brute",
  "event": "compile_failed",
  "duration_ms": 1234,
  "model": "...",
  "runner_image": "cpp17-runner:v1"
}
```

---

## 16. 部署方案

### 16.1 开发环境

推荐使用 Docker Compose：
- frontend
- api
- worker
- redis
- postgres
- minio
- runner

### 16.2 生产环境

推荐 Kubernetes：
- `frontend-deployment`
- `api-deployment`
- `worker-deployment`
- `runner-deployment`
- `redis`
- `postgres`（托管优先）
- `object-storage`（托管优先）

### 16.3 为什么生产建议 K8s

因为后续你一定会遇到：
- Runner 横向扩容；
- 不同语言镜像；
- 不同资源规格；
- 异步任务峰值；
- 灰度发布；
- 成本治理。

K8s 对这些问题更自然。

### 16.4 环境变量建议

- `DATABASE_URL`
- `REDIS_URL`
- `S3_ENDPOINT`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `MODEL_API_KEY`
- `RUNNER_BASE_URL`
- `MAX_DUEL_ROUNDS`
- `DEFAULT_TIME_LIMIT_MS`
- `DEFAULT_MEMORY_LIMIT_MB`

---

## 17. 项目目录建议（Monorepo）

```text
repo/
  apps/
    web/                 # Next.js frontend
    api/                 # FastAPI
    worker/              # Celery worker
    runner/              # sandbox runner service
  packages/
    shared-types/        # TS/Python schema sync or OpenAPI generated types
    prompt-templates/    # agent prompts
    problem-spec/        # parsing & schema definitions
  infra/
    docker/
    k8s/
    terraform/
  docs/
    architecture/
    api/
    prompts/
```

### 17.1 Monorepo 优势
- 前后端版本同步；
- OpenAPI / types 共享；
- CI/CD 简化；
- agent prompt、schema、runner config 统一管理。

---

## 18. 开发里程碑

### Phase 0：技术预研（1 周）
目标：证明“题面 → brute/gen → 对拍”可行。

交付：
- CLI 原型
- 3 道题回归测试
- 单机 runner 原型

### Phase 1：MVP 后端闭环（2 周）
交付：
- ProblemSpec 抽取
- brute/gen 生成
- 编译与对拍 API
- 单机 Redis/Postgres/MinIO

### Phase 2：前端工作台（2 周）
交付：
- 项目页
- 题面输入
- 代码展示
- 任务状态与结果展示

### Phase 3：安全与稳定性（1~2 周）
交付：
- Rootless Docker + gVisor
- 限时/限内存/限输出
- 基础监控

### Phase 4：质量增强（2 周）
交付：
- Repair 流程
- 反例最小化
- README/复现包下载

---

## 19. 测试方案

### 19.1 单元测试
- 题面切分
- ProblemSpec schema 校验
- compare 逻辑
- counterexample shrinking

### 19.2 集成测试
- 题面上传 → 生成 → 编译 → 自测
- 用户代码上传 → 对拍 → 返回失败样例

### 19.3 E2E 测试
Playwright 覆盖：
- 新建项目
- 粘贴题面
- 生成资产
- 上传用户代码
- 查看错误样例

### 19.4 回归题集
建议维护一个内部 `golden set`：
- 数组题
- 图题
- DP 题
- 多组测试题
- 容易误读输入的题
- 边界很多的题

每次模型提示词或 runner 升级都跑回归。

---

## 20. 成本控制建议

### 20.1 模型成本
- ProblemSpec 抽取用高质量模型；
- generator/repair/explain 用中成本模型；
- 对相同题面做缓存；
- 对相同 problem hash 复用生成结果。

### 20.2 执行成本
- brute 仅在小规模跑；
- 对拍分阶段递增规模；
- 出现失败立即停止；
- runner 镜像按语言分层缓存。

### 20.3 存储成本
- 原始日志设置 TTL；
- 大输出仅保留失败样例；
- 成功对拍默认不保留全部中间输入。

---

## 21. 风险与规避

### 风险 1：模型误读题意
**规避：** 中间态 ProblemSpec 可视化、用户可编辑、低置信度字段高亮。

### 风险 2：暴力解其实不正确
**规避：** 多轮自测、样例验证、模型自评、人工可编辑。

### 风险 3：沙箱被打穿
**规避：** rootless + gVisor + no-network + 只读根文件系统 + runner 独立部署。

### 风险 4：任务耗时太长
**规避：** 异步队列、结果缓存、分阶段对拍、资源配额。

### 风险 5：前端状态复杂
**规避：** React Query + 明确任务状态机 + 统一 Task API。

---

## 22. 推荐实现顺序（非常重要）

不要一上来就做完整 Web 产品，推荐按这个顺序推进：

### 第一阶段：CLI 验证核心闭环
先做命令行版本：
1. 输入题面文本文件；
2. 输出 `brute.cpp` + `gen.cpp`；
3. 输入用户代码；
4. 本地对拍出失败样例。

### 第二阶段：后端 API 化
把 CLI 包装成：
- `/generate`
- `/duel`
- `/tasks/:id`

### 第三阶段：前端工作台
再做：
- 题面编辑器
- 代码预览
- 日志页
- 错误样例页

### 第四阶段：安全与生产化
最后再上：
- Runner 集群
- gVisor
- 告警
- S3
- 用户系统

这个顺序能显著降低失败概率。

---

## 23. 我给你的最终技术决策

如果让我直接拍板，这个项目我会这样定：

### 前端
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- Monaco Editor
- TanStack Query
- Zustand

### 后端
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic

### 异步任务
- Celery
- Redis

### 数据层
- PostgreSQL
- MinIO（dev）/ S3（prod）

### 执行层
- 独立 Runner Service
- Rootless Docker
- gVisor

### 解析与智能
- Python Agent pipeline
- ProblemSpec 中间态
- 多阶段生成 + 编译自检 + 限次修复

### 测试
- Pytest
- Playwright

### 部署
- Docker Compose（dev）
- Kubernetes（prod）

---

## 24. MVP 任务清单（可直接开工）

### 后端
- [ ] 建立 FastAPI 项目骨架
- [ ] 设计 Project / Problem / Artifact / Task 表
- [ ] 完成题面上传接口
- [ ] 完成 ProblemSpec 抽取接口
- [ ] 完成 brute/gen 生成任务
- [ ] 完成编译 API
- [ ] 完成对拍 API
- [ ] 完成结果持久化

### Runner
- [ ] 建立 cpp runner 镜像
- [ ] 实现 compile endpoint
- [ ] 实现 run endpoint
- [ ] 加入 timeout / memory / output limit
- [ ] 加入 gVisor 运行时

### 前端
- [ ] 新建项目页
- [ ] 题面输入页
- [ ] ProblemSpec 预览/编辑页
- [ ] 生成资产页
- [ ] 用户代码上传页
- [ ] 对拍结果页

### 测试
- [ ] 选 10 道题做 golden set
- [ ] 写后端单测
- [ ] 写 runner 集成测试
- [ ] 写 Playwright 主流程 E2E

---

## 25. 附：MVP 接口返回示例

### 25.1 发起生成任务返回

```json
{
  "task_id": "tsk_123",
  "status": "queued"
}
```

### 25.2 查询任务返回

```json
{
  "task_id": "tsk_123",
  "type": "generate",
  "status": "self_testing",
  "progress": 76,
  "current_stage": "compile_generator",
  "logs": [
    {
      "time": "2026-03-24T10:00:00Z",
      "level": "info",
      "message": "generator compiled successfully"
    }
  ]
}
```

### 25.3 对拍失败返回

```json
{
  "status": "counterexample_found",
  "round": 37,
  "seed": 104729,
  "input": "4\n1 3 2 4\n",
  "expected_output": "3\n",
  "actual_output": "4\n",
  "stderr": "",
  "timed_out": false,
  "minimized": true,
  "explanation": "你的程序假设数组单调时答案可直接取末尾，但在该输入下不成立。"
}
```

---

## 26. 结论

这是一个非常适合做成产品的 Agent 系统，但它的难点不在“调一个模型生成代码”，而在于：

1. **题面结构化抽取是否稳定**；
2. **参考暴力解是否真的可靠**；
3. **不可信代码执行是否足够安全**；
4. **整条链路是否可观测、可重试、可解释**。

因此，最优路线不是“先做一个花哨前端”，而是：

> **先用 Python 把 Agent + 对拍内核做扎实，再用 Next.js 做成一个像 IDE 的工作台，最后用独立 Runner + gVisor 把执行层收口。**

如果按本文档落地，MVP 就已经可以覆盖大多数“题面 → 暴力对拍 → 错误样例”需求，后续也能平滑扩展到多语言、多题型和团队协作。

---

## 27. 参考依据（技术选型）

- Next.js 官方文档：App Router 适合作为现代 React 应用主路由架构。
- FastAPI 官方文档：内置 BackgroundTasks 适合轻量后台工作，长任务应由专门任务系统承接。
- Monaco Editor 官方文档：Monaco 为 VS Code 同源浏览器编辑器，适合代码编辑工作台。
- Redis 官方文档：Streams/队列能力适合后台 worker 消费模型。
- gVisor 官方文档：gVisor 适用于运行不可信工作负载并提供额外隔离层。
- Docker 官方文档：Rootless mode 可降低 daemon 与容器运行的主机风险面。
- Pandoc 官方文档：可在 Markdown / HTML / LaTeX / docx 等格式间转换，适合题面归一化。
- KaTeX 官方文档：浏览器端高性能数学公式渲染。
- PostgreSQL 官方文档：`jsonb` 与全文检索能力适合 ProblemSpec 和任务日志场景。
- Playwright 官方文档：适合现代 Web 应用端到端测试。
