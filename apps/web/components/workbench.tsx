"use client";

import { useEffect, useMemo, useState } from "react";

type ArtifactRecord = {
  type: string;
  language: string;
  code: string;
};

type DuelFailure = {
  round: number;
  seed: number;
  mode: string;
  size: number;
  reason: string;
  input: string;
  expected_output: string;
  actual_output: string;
  stderr: string;
  timed_out: boolean;
  user_exit_code?: number | null;
  brute_exit_code?: number | null;
};

type DuelResult = {
  status: string;
  rounds_requested: number;
  rounds_completed: number;
  compile_logs: Record<string, string>;
  failure?: DuelFailure | null;
  summary: string;
  warnings: string[];
  created_at: string;
};

type ProjectRecord = {
  id: string;
  name: string;
  status: string;
  raw_problem_content?: string | null;
  problem_spec?: unknown;
  artifacts: Record<string, ArtifactRecord>;
  last_duel_result?: DuelResult | null;
  task_ids: string[];
  updated_at: string;
};

type TaskRecord = {
  id: string;
  project_id: string;
  type: string;
  status: string;
  progress: number;
  current_stage?: string | null;
  logs: Array<{ level: string; message: string; time: string }>;
  result?: Record<string, unknown> | null;
  error?: string | null;
};

type RuntimeInfo = {
  api_time: string;
  openai: {
    configured: boolean;
    sdk_installed: boolean;
    provider_available: boolean;
    model: string;
    base_url?: string | null;
    reasoning_effort?: string | null;
  };
  queue: {
    requested_backend: string;
    active_backend: string;
    worker_pool: string;
  };
  redis: {
    host: string;
    port: number;
    password_configured: boolean;
  };
  toolchain: {
    cxx: string;
    codegen_provider: string;
  };
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export function Workbench() {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [activeArtifact, setActiveArtifact] = useState("brute");
  const [projectName, setProjectName] = useState("Demo Project");
  const [problemText, setProblemText] = useState(`# A + B Problem

题目描述
给定两个整数，输出它们的和。

输入格式
\`\`\`text
a b
\`\`\`

输出格式
\`\`\`text
输出一个整数
\`\`\`

样例输入
\`\`\`text
1 2
\`\`\`

样例输出
\`\`\`text
3
\`\`\`
`);
  const [userCode, setUserCode] = useState(`#include <bits/stdc++.h>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    long long a, b;
    if (!(cin >> a >> b)) return 0;
    cout << a + b << "\\n";
    return 0;
}
`);
  const [provider, setProvider] = useState("auto");
  const [selfTest, setSelfTest] = useState(true);
  const [repairRounds, setRepairRounds] = useState("1");
  const [duelRounds, setDuelRounds] = useState("50");
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  useEffect(() => {
    void runBusy(async () => {
      await refreshDashboard();
    });
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      return;
    }
    const selected = projects.find((project) => project.id === selectedProjectId);
    if (!selected) {
      return;
    }
    setProblemText(selected.raw_problem_content ?? "");
    setUserCode(selected.artifacts.user_solution?.code ?? userCode);
    const nextActiveArtifact = pickDefaultArtifact(selected.artifacts, activeArtifact);
    if (nextActiveArtifact !== activeArtifact) {
      setActiveArtifact(nextActiveArtifact);
    }
  }, [selectedProjectId, projects]);

  useEffect(() => {
    if (!task || !["queued", "running"].includes(task.status)) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const nextTask = await apiFetch<TaskRecord>(`/api/tasks/${task.id}`);
        setTask(nextTask);
        if (!["queued", "running"].includes(nextTask.status)) {
          await refreshProjects(selectedProjectId || nextTask.project_id);
        }
      } catch (pollError) {
        setError(asErrorMessage(pollError));
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [task, selectedProjectId]);

  async function refreshProjects(preferredProjectId?: string) {
    const nextProjects = await apiFetch<ProjectRecord[]>("/api/projects");
    setProjects(nextProjects);
    const target = preferredProjectId ?? selectedProjectId ?? nextProjects[0]?.id ?? "";
    if (target) {
      setSelectedProjectId(target);
    } else if (nextProjects[0]?.id) {
      setSelectedProjectId(nextProjects[0].id);
    }
  }

  async function refreshRuntime() {
    const nextRuntime = await apiFetch<RuntimeInfo>("/api/runtime");
    setRuntime(nextRuntime);
  }

  async function refreshDashboard(preferredProjectId?: string) {
    await Promise.all([refreshProjects(preferredProjectId), refreshRuntime()]);
  }

  async function createProject() {
    await runBusy(async () => {
      const project = await apiFetch<ProjectRecord>("/api/projects", {
        method: "POST",
        body: JSON.stringify({ name: projectName }),
      });
      setSelectedProjectId(project.id);
      await refreshProjects(project.id);
    });
  }

  async function saveProblem() {
    if (!selectedProjectId) {
      setError("先创建或选择一个项目。");
      return;
    }
    await runBusy(async () => {
      await apiFetch<ProjectRecord>(`/api/projects/${selectedProjectId}/problem-text`, {
        method: "POST",
        body: JSON.stringify({ content: problemText, format: "markdown" }),
      });
      await refreshProjects(selectedProjectId);
    });
  }

  async function saveUserSolution() {
    if (!selectedProjectId) {
      setError("先创建或选择一个项目。");
      return;
    }
    await runBusy(async () => {
      await apiFetch<ProjectRecord>(`/api/projects/${selectedProjectId}/artifacts`, {
        method: "POST",
        body: JSON.stringify({
          type: "user_solution",
          language: "cpp",
          code: userCode,
        }),
      });
      await refreshProjects(selectedProjectId);
    });
  }

  async function startParse() {
    if (!selectedProjectId) {
      setError("先创建或选择一个项目。");
      return;
    }
    await runBusy(async () => {
      const response = await apiFetch<{ task: TaskRecord }>(
        `/api/projects/${selectedProjectId}/parse-async`,
        { method: "POST" },
      );
      setTask(response.task);
    });
  }

  async function startGenerate() {
    if (!selectedProjectId) {
      setError("先创建或选择一个项目。");
      return;
    }
    await runBusy(async () => {
      const response = await apiFetch<{ task: TaskRecord }>(
        `/api/projects/${selectedProjectId}/generate-artifacts-async`,
        {
          method: "POST",
          body: JSON.stringify({
            provider,
            self_test: selfTest,
            repair_rounds: clampInt(repairRounds, 1, 0, 2),
          }),
        },
      );
      setTask(response.task);
    });
  }

  async function startDuel() {
    if (!selectedProjectId) {
      setError("先创建或选择一个项目。");
      return;
    }
    await runBusy(async () => {
      const response = await apiFetch<{ task: TaskRecord }>(
        `/api/projects/${selectedProjectId}/duel-async`,
        {
          method: "POST",
          body: JSON.stringify({
            rounds: Number(duelRounds) || 50,
            time_limit_ms: 1000,
            memory_limit_mb: 256,
            generator_mode: ["small", "edge", "random"],
            stop_on_first_fail: true,
          }),
        },
      );
      setTask(response.task);
    });
  }

  async function runBusy(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (actionError) {
      setError(asErrorMessage(actionError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <section className="hero panel">
        <div className="heroGlow" />
        <div className="heroContent">
          <div className="eyebrow">AlgoHlper / Workbench</div>
          <div className="header">
            <div>
              <h1>算法对拍工作台</h1>
              <div className="muted">
                项目、题面、代码生成、异步任务和失败样例放在同一个工作区里。
              </div>
            </div>
            <div className="headerMeta">
              <StatusBadge label={`API ${API_BASE_URL}`} tone="neutral" />
              <StatusBadge
                label={runtime?.openai.provider_available ? "OpenAI 已就绪" : "OpenAI 未就绪"}
                tone={runtime?.openai.provider_available ? "success" : "warning"}
              />
              <StatusBadge
                label={busy ? "请求处理中" : "空闲"}
                tone={busy ? "running" : "success"}
              />
            </div>
          </div>
        </div>
      </section>

      {error ? (
        <section className="panel banner bannerError">
          <div className="bannerTitle">请求失败</div>
          <div>{error}</div>
        </section>
      ) : null}

      <section className="layout">
        <aside className="sidebar stack">
          <section className="panel stack sidebarCard">
            <div className="panelHeading">
              <div>
                <h2>新建项目</h2>
                <p className="muted">先建项目，再保存题面并发起异步任务。</p>
              </div>
            </div>
            <label className="field">
              <span className="fieldLabel">项目名</span>
              <input
                className="input"
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="项目名"
              />
            </label>
            <div className="buttonRow">
              <button className="button" onClick={() => void createProject()} disabled={busy}>
                新建项目
              </button>
              <button
                className="button secondary"
                onClick={() => void runBusy(async () => refreshDashboard())}
                disabled={busy}
              >
                刷新列表
              </button>
            </div>
          </section>

          <section className="panel stack sidebarCard">
            <div className="panelHeading">
              <div>
                <h2>项目列表</h2>
                <p className="muted">点击切换上下文。</p>
              </div>
              <div className="pill">{projects.length} 项</div>
            </div>

            <div className="projectList">
              {projects.map((project) => (
                <button
                  key={project.id}
                  type="button"
                  className={`projectItem ${project.id === selectedProjectId ? "active" : ""}`}
                  onClick={() => setSelectedProjectId(project.id)}
                >
                  <div className="projectTop">
                    <strong>{project.name}</strong>
                    <StatusBadge label={project.status} tone={getStatusTone(project.status)} />
                  </div>
                  <div className="muted mono">{project.id}</div>
                  <div className="projectMeta">updated {formatTime(project.updated_at)}</div>
                </button>
              ))}
              {projects.length === 0 ? <div className="emptyState">还没有项目，先在上面建一个。</div> : null}
            </div>
          </section>

          <section className="panel stack sidebarCard">
            <div className="panelHeading">
              <div>
                <h2>运行环境</h2>
                <p className="muted">当前 API、OpenAI、队列和本地工具链状态。</p>
              </div>
              <button
                className="button secondary buttonSmall"
                onClick={() => void runBusy(async () => refreshRuntime())}
                disabled={busy}
              >
                刷新
              </button>
            </div>
            <RuntimePanel runtime={runtime} />
          </section>
        </aside>

        <section className="content stack">
          <section className="metricGrid">
            <MetricCard
              title="当前项目"
              value={selectedProject?.name ?? "未选择"}
              meta={selectedProject?.id ?? "请先在左侧选择项目"}
            />
            <MetricCard
              title="项目状态"
              value={selectedProject?.status ?? "draft"}
              meta={`artifacts ${Object.keys(selectedProject?.artifacts ?? {}).length}`}
              tone={getStatusTone(selectedProject?.status)}
            />
            <MetricCard
              title="最近任务"
              value={task?.type ?? "none"}
              meta={task ? `${task.status} / ${task.current_stage ?? "-"}` : "等待任务"}
              tone={getStatusTone(task?.status)}
            />
            <MetricCard
              title="对拍轮数"
              value={duelRounds}
              meta="当前发起参数"
            />
            <MetricCard
              title="生成策略"
              value={`${provider} / ${selfTest ? "self-test" : "fast"}`}
              meta={`repair ${clampInt(repairRounds, 1, 0, 2)}`}
              tone={runtime?.openai.provider_available ? "success" : "warning"}
            />
            <MetricCard
              title="任务后端"
              value={runtime?.queue.active_backend ?? "unknown"}
              meta={`requested ${runtime?.queue.requested_backend ?? "-"}`}
              tone={getStatusTone(runtime?.queue.active_backend)}
            />
          </section>

          <section className="panel stack panelLarge">
            <div className="panelHeading">
              <div>
                <h2>编辑区</h2>
                <p className="muted">先保存题面和用户代码，再触发解析 / 生成 / 对拍。</p>
              </div>
            </div>

            <div className="toolbar">
              <div className="toolbarGroup">
                <button className="button" onClick={() => void saveProblem()} disabled={busy || !selectedProjectId}>
                  保存题面
                </button>
                <button className="button secondary" onClick={() => void startParse()} disabled={busy || !selectedProjectId}>
                  异步解析
                </button>
              </div>

              <div className="toolbarGroup">
                <label className="field compactField">
                  <span className="fieldLabel">生成器</span>
                  <select className="select" value={provider} onChange={(event) => setProvider(event.target.value)}>
                    <option value="auto">auto</option>
                    <option value="template">template</option>
                    <option value="openai">openai</option>
                  </select>
                </label>
                <label className="field compactField fieldShort">
                  <span className="fieldLabel">回修轮数</span>
                  <input
                    className="input"
                    value={repairRounds}
                    onChange={(event) => setRepairRounds(event.target.value)}
                  />
                </label>
                <label className="toggleField">
                  <input
                    type="checkbox"
                    checked={selfTest}
                    onChange={(event) => setSelfTest(event.target.checked)}
                  />
                  <span>生成后自检</span>
                </label>
                <button className="button secondary" onClick={() => void startGenerate()} disabled={busy || !selectedProjectId}>
                  异步生成
                </button>
              </div>

              <div className="toolbarGroup">
                <button className="button ghost" onClick={() => void saveUserSolution()} disabled={busy || !selectedProjectId}>
                  保存用户代码
                </button>
                <label className="field compactField fieldShort">
                  <span className="fieldLabel">轮数</span>
                  <input
                    className="input"
                    value={duelRounds}
                    onChange={(event) => setDuelRounds(event.target.value)}
                  />
                </label>
                <button className="button ghost" onClick={() => void startDuel()} disabled={busy || !selectedProjectId}>
                  异步对拍
                </button>
              </div>
            </div>

            <div className="editorGrid">
              <div className="editorCard">
                <div className="editorHeader">
                  <div>
                    <h3>题面</h3>
                    <div className="muted">Markdown / text / LaTeX 文本输入。</div>
                  </div>
                </div>
                <textarea className="textarea editorArea" value={problemText} onChange={(event) => setProblemText(event.target.value)} />
              </div>
              <div className="editorCard">
                <div className="editorHeader">
                  <div>
                    <h3>用户代码</h3>
                    <div className="muted">当前先用纯文本编辑，后面再切 Monaco。</div>
                  </div>
                </div>
                <textarea className="textarea editorArea" value={userCode} onChange={(event) => setUserCode(event.target.value)} />
              </div>
            </div>
          </section>

          <section className="twoCol">
            <section className="panel stack panelLarge">
              <div className="panelHeading">
                <div>
                  <h2>当前任务</h2>
                  <p className="muted">异步任务状态、阶段和日志。</p>
                </div>
                {task ? (
                  <StatusBadge
                    label={`${task.status} · ${task.progress}%`}
                    tone={getStatusTone(task.status)}
                  />
                ) : null}
              </div>
              {task ? (
                <>
                  <div className="metaRow">
                    <StatusBadge label={task.type} tone="neutral" />
                    <StatusBadge label={task.current_stage ?? "-"} tone="neutral" />
                    <StatusBadge label={`progress ${task.progress}%`} tone="running" />
                  </div>
                  {task.error ? <div className="banner bannerError">{task.error}</div> : null}
                  <TaskLogsPanel logs={task.logs} />
                </>
              ) : (
                <div className="emptyState">还没有任务。先保存题面，然后点“异步解析”或“异步生成”。</div>
              )}
            </section>

            <section className="panel stack panelLarge">
              <div className="panelHeading">
                <div>
                  <h2>项目结构</h2>
                  <p className="muted">ProblemSpec、产物和项目元信息。</p>
                </div>
                {selectedProject ? (
                  <StatusBadge label={selectedProject.status} tone={getStatusTone(selectedProject.status)} />
                ) : null}
              </div>
              {selectedProject ? (
                <>
                  <div className="metaRow">
                    <StatusBadge label={selectedProject.id} tone="neutral" />
                    <StatusBadge
                      label={`${Object.keys(selectedProject.artifacts ?? {}).length} artifacts`}
                      tone="neutral"
                    />
                  </div>
                  <div className="pre projectSpec">
                    {selectedProject.problem_spec
                      ? JSON.stringify(selectedProject.problem_spec, null, 2)
                      : "ProblemSpec 尚未生成"}
                  </div>
                </>
              ) : (
                <div className="emptyState">请选择项目。</div>
              )}
            </section>
          </section>

          <section className="twoCol">
            <section className="panel stack panelLarge">
              <div className="panelHeading">
                <div>
                  <h2>生成产物</h2>
                  <p className="muted">切换不同产物查看当前代码。</p>
                </div>
              </div>
              <ArtifactTabs
                project={selectedProject}
                activeArtifact={activeArtifact}
                onChange={setActiveArtifact}
              />
            </section>

            <section className="panel stack panelLarge">
              <div className="panelHeading">
                <div>
                  <h2>对拍结果</h2>
                  <p className="muted">首个失败样例、输出差异和编译日志。</p>
                </div>
              </div>
              <DuelResultPanel result={selectedProject?.last_duel_result ?? null} />
            </section>
          </section>
        </section>
      </section>
    </main>
  );
}

function RuntimePanel({ runtime }: { runtime: RuntimeInfo | null }) {
  if (!runtime) {
    return <div className="emptyState">正在读取运行环境…</div>;
  }

  const queueFallback =
    runtime.queue.requested_backend !== runtime.queue.active_backend
      ? `已从 ${runtime.queue.requested_backend} 回退到 ${runtime.queue.active_backend}`
      : "";

  return (
    <div className="stack">
      <div className="runtimeGrid">
        <InfoItem label="OpenAI" value={runtime.openai.provider_available ? "ready" : "not ready"} />
        <InfoItem label="Model" value={runtime.openai.model || "-"} />
        <InfoItem label="Queue" value={runtime.queue.active_backend} />
        <InfoItem label="C++" value={runtime.toolchain.cxx} />
      </div>

      <div className="stack subtleCard">
        <div className="metaRow">
          <StatusBadge
            label={runtime.openai.provider_available ? "OpenAI 可用" : "OpenAI 不可用"}
            tone={runtime.openai.provider_available ? "success" : "warning"}
          />
          <StatusBadge
            label={runtime.openai.sdk_installed ? "SDK 已安装" : "SDK 未安装"}
            tone={runtime.openai.sdk_installed ? "success" : "warning"}
          />
        </div>
        <div className="muted">base_url：{runtime.openai.base_url ?? "官方默认"}</div>
        <div className="muted">reasoning：{runtime.openai.reasoning_effort ?? "-"}</div>
      </div>

      <div className="stack subtleCard">
        <div className="metaRow">
          <StatusBadge label={`queue ${runtime.queue.active_backend}`} tone={getStatusTone(runtime.queue.active_backend)} />
          <StatusBadge label={`pool ${runtime.queue.worker_pool}`} tone="neutral" />
        </div>
        <div className="muted">
          Redis：{runtime.redis.host}:{runtime.redis.port}
          {runtime.redis.password_configured ? " / 已配置密码" : " / 未配置密码"}
        </div>
        <div className="muted">默认 provider：{runtime.toolchain.codegen_provider}</div>
      </div>

      {queueFallback ? <div className="banner bannerWarn">{queueFallback}</div> : null}
    </div>
  );
}

function MetricCard({
  title,
  value,
  meta,
  tone = "neutral",
}: {
  title: string;
  value: string;
  meta: string;
  tone?: BadgeTone;
}) {
  return (
    <section className={`metricCard tone-${tone}`}>
      <div className="metricTitle">{title}</div>
      <div className="metricValue">{value}</div>
      <div className="metricMeta">{meta}</div>
    </section>
  );
}

function ArtifactTabs({
  project,
  activeArtifact,
  onChange,
}: {
  project: ProjectRecord | null;
  activeArtifact: string;
  onChange: (artifactName: string) => void;
}) {
  const artifactEntries = getArtifactEntries(project?.artifacts ?? {});
  const artifact = project?.artifacts?.[activeArtifact];

  return (
    <div className="stack">
      <div className="tabs">
        {artifactEntries.map(([artifactName, value]) => (
          <button
            key={artifactName}
            type="button"
            className={`tabButton ${artifactName === activeArtifact ? "active" : ""}`}
            onClick={() => onChange(artifactName)}
          >
            <span>{artifactName}</span>
            <span className="muted">({value.language})</span>
          </button>
        ))}
      </div>
      <div className="code artifactCode">{artifact?.code ?? "当前没有可预览的产物。"}</div>
    </div>
  );
}

function DuelResultPanel({ result }: { result: DuelResult | null }) {
  if (!result) {
    return <div className="muted">还没有对拍结果</div>;
  }

  const failure = result.failure;

  return (
    <div className="stack">
      <div className="metaRow">
        <StatusBadge label={result.status} tone={getStatusTone(result.status)} />
        <StatusBadge label={`rounds ${result.rounds_completed}/${result.rounds_requested}`} tone="neutral" />
      </div>
      <div>{result.summary}</div>
      {result.warnings.length > 0 ? (
        <div className="stack warningList">
          {result.warnings.map((warning) => (
            <div key={warning} className="muted">
              - {warning}
            </div>
          ))}
        </div>
      ) : null}
      {failure ? (
        <>
          <div className="card stack">
            <div className="metaRow">
              <StatusBadge label="失败样例" tone="error" />
              <StatusBadge label={humanizeReason(failure.reason)} tone="error" />
            </div>
            <div className="cardGrid">
              <InfoItem label="round" value={String(failure.round)} />
              <InfoItem label="seed" value={String(failure.seed)} />
              <InfoItem label="mode" value={failure.mode} />
              <InfoItem label="size" value={String(failure.size)} />
            </div>
            {failure.stderr ? <div className="pre">{failure.stderr}</div> : null}
          </div>
          <div className="stack">
            <h3>输入</h3>
            <div className="pre">{failure.input || "(empty)"}</div>
          </div>
          <DiffViewer expected={failure.expected_output} actual={failure.actual_output} />
          {Object.keys(result.compile_logs).length > 0 ? (
            <div className="stack">
              <h3>编译日志</h3>
              {Object.entries(result.compile_logs).map(([name, log]) => (
                <div key={name} className="stack">
                  <div className="pill">{name}</div>
                  <div className="pre">{log || "(empty)"}</div>
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <div className="banner bannerSuccess">本轮没有发现失败样例。</div>
      )}
    </div>
  );
}

function DiffViewer({
  expected,
  actual,
}: {
  expected: string;
  actual: string;
}) {
  const expectedLines = normalizeLines(expected);
  const actualLines = normalizeLines(actual);
  const maxLength = Math.max(expectedLines.length, actualLines.length);

  return (
    <div className="stack">
      <h3>输出对比</h3>
      <div className="diffGrid">
        <div className="diffCol">
          <div className="pill">expected</div>
          <div className="pre diffPre">
            {Array.from({ length: maxLength }, (_, index) => {
              const left = expectedLines[index] ?? "";
              const right = actualLines[index] ?? "";
              const same = left === right;
              return (
                <div key={`left-${index}`} className={`diffLine ${same ? "same" : "removed"}`}>
                  <span className="lineNo">{index + 1}</span>
                  <span>{left || " "}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="diffCol">
          <div className="pill">actual</div>
          <div className="pre diffPre">
            {Array.from({ length: maxLength }, (_, index) => {
              const left = expectedLines[index] ?? "";
              const right = actualLines[index] ?? "";
              const same = left === right;
              return (
                <div key={`right-${index}`} className={`diffLine ${same ? "same" : "added"}`}>
                  <span className="lineNo">{index + 1}</span>
                  <span>{right || " "}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function TaskLogsPanel({
  logs,
}: {
  logs: Array<{ level: string; message: string; time: string }>;
}) {
  if (logs.length === 0) {
    return <div className="emptyState">暂无日志。</div>;
  }

  return (
    <div className="logList">
      {logs.map((log, index) => (
        <div key={`${log.time}-${index}`} className="logItem">
          <div className={`logDot tone-${getLogTone(log.level)}`} />
          <div className="logContent">
            <div className="logMeta">
              <span className="mono">{log.level}</span>
              <span className="muted">{formatTime(log.time)}</span>
            </div>
            <div>{log.message}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="infoItem">
      <div className="infoLabel">{label}</div>
      <div className="infoValue">{value}</div>
    </div>
  );
}

function StatusBadge({
  label,
  tone,
}: {
  label: string;
  tone: BadgeTone;
}) {
  return <span className={`statusBadge tone-${tone}`}>{label}</span>;
}

function asErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function clampInt(value: string, fallback: number, min: number, max: number): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, parsed));
}

function getArtifactEntries(artifacts: Record<string, ArtifactRecord>): Array<[string, ArtifactRecord]> {
  const preferredOrder = ["brute", "generator", "user_solution", "compare", "readme"];
  return Object.entries(artifacts).sort(
    ([left], [right]) => preferredOrder.indexOf(left) - preferredOrder.indexOf(right),
  );
}

function pickDefaultArtifact(artifacts: Record<string, ArtifactRecord>, current: string): string {
  if (artifacts[current]) {
    return current;
  }
  const next = getArtifactEntries(artifacts)[0]?.[0];
  return next ?? "brute";
}

function normalizeLines(text: string): string[] {
  return text.replace(/\r\n/g, "\n").split("\n");
}

function humanizeReason(reason: string): string {
  switch (reason) {
    case "wrong_answer":
      return "Wrong Answer";
    case "user_runtime_error":
      return "User Runtime Error";
    case "user_timed_out":
      return "User Timed Out";
    case "generator_runtime_error":
      return "Generator Runtime Error";
    case "brute_runtime_error":
      return "Brute Runtime Error";
    default:
      return reason;
  }
}

type BadgeTone = "neutral" | "success" | "running" | "warning" | "error";

function getStatusTone(status?: string | null): BadgeTone {
  switch (status) {
    case "completed":
    case "ready":
    case "parsed":
    case "counterexample_found":
    case "celery":
      return "success";
    case "running":
    case "dueling":
    case "queued":
    case "generating":
    case "self_testing":
      return "running";
    case "inprocess":
      return "warning";
    case "failed":
    case "error":
      return "error";
    case "draft":
      return "warning";
    default:
      return "neutral";
  }
}

function getLogTone(level: string): BadgeTone {
  switch (level) {
    case "error":
      return "error";
    case "warning":
      return "warning";
    default:
      return "running";
  }
}

function formatTime(value?: string): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}
