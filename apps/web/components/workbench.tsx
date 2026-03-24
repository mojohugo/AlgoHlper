"use client";

import { useEffect, useMemo, useState } from "react";

import { CodeEditor } from "./code-editor";
import { CopyButton } from "./copy-button";
import { ProblemSpecEditor } from "./problem-spec-editor";

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

type ProblemSample = {
  input: string;
  output: string;
};

type ProblemSpec = {
  title: string;
  statement: string;
  input_format: string;
  output_format: string;
  constraints: Record<string, string>;
  samples: ProblemSample[];
  problem_type_guess: string[];
  special_notes: string[];
  parse_confidence: Record<string, number>;
};

type ProjectRecord = {
  id: string;
  name: string;
  status: string;
  raw_problem_content?: string | null;
  problem_spec?: ProblemSpec | null;
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

type QuickRunResult = {
  compile_ok: boolean;
  compile_log: string;
  exit_code?: number | null;
  stdout: string;
  stderr: string;
  time_ms: number;
  timed_out: boolean;
};

type WorkspaceTab = "overview" | "edit" | "assets" | "run";

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
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("edit");
  const [activeArtifact, setActiveArtifact] = useState("brute");
  const [projectName, setProjectName] = useState("Demo Project");
  const [specDraft, setSpecDraft] = useState<ProblemSpec>(emptyProblemSpec());
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
  const [quickInput, setQuickInput] = useState("");
  const [quickRunTimeLimitMs, setQuickRunTimeLimitMs] = useState("1000");
  const [quickRunResult, setQuickRunResult] = useState<QuickRunResult | null>(null);
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
    setSpecDraft(cloneProblemSpec(selected.problem_spec));
    setQuickRunResult(null);
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

  async function saveProblemSpec() {
    if (!selectedProjectId) {
      setError("先创建或选择一个项目。");
      return;
    }
    await runBusy(async () => {
      await apiFetch<ProjectRecord>(`/api/projects/${selectedProjectId}/problem-spec`, {
        method: "PUT",
        body: JSON.stringify(specDraft),
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
      setWorkspaceTab("assets");
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
      setWorkspaceTab("assets");
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
      setWorkspaceTab("run");
    });
  }

  async function runQuickUserCode() {
    if (!selectedProjectId) {
      setError("先创建或选择一个项目。");
      return;
    }
    await runBusy(async () => {
      const response = await apiFetch<QuickRunResult>(
        `/api/projects/${selectedProjectId}/run-user`,
        {
          method: "POST",
          body: JSON.stringify({
            code: userCode,
            input: quickInput,
            time_limit_ms: clampInt(quickRunTimeLimitMs, 1000, 10, 60_000),
          }),
        },
      );
      setQuickRunResult(response);
      setWorkspaceTab("edit");
    });
  }

  function fillQuickInputFromFailure() {
    const failureInput = selectedProject?.last_duel_result?.failure?.input ?? "";
    setQuickInput(failureInput);
    setQuickRunResult(null);
    setWorkspaceTab("edit");
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
                现在按工作流拆成概览 / 编辑 / 生成资产 / 对拍运行四个分区，减少来回切换和误点。
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
          <WorkspaceTabs active={workspaceTab} onChange={setWorkspaceTab} />

          {workspaceTab === "overview" ? (
            <>
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
                <MetricCard
                  title="最近对拍"
                  value={selectedProject?.last_duel_result?.status ?? "none"}
                  meta={
                    selectedProject?.last_duel_result
                      ? `${selectedProject.last_duel_result.rounds_completed}/${selectedProject.last_duel_result.rounds_requested}`
                      : "还没有运行"
                  }
                  tone={getStatusTone(selectedProject?.last_duel_result?.status)}
                />
              </section>

              <section className="twoCol">
                <TaskPanel task={task} />
                <ProjectSummaryPanel
                  project={selectedProject}
                  onOpenEdit={() => setWorkspaceTab("edit")}
                  onOpenAssets={() => setWorkspaceTab("assets")}
                  onOpenRun={() => setWorkspaceTab("run")}
                />
              </section>

              <section className="twoCol">
                <section className="panel stack panelLarge">
                  <div className="panelHeading">
                    <div>
                      <h2>运行环境摘要</h2>
                      <p className="muted">保留最常用的配置状态，排查环境问题时看这里。</p>
                    </div>
                  </div>
                  <RuntimePanel runtime={runtime} />
                </section>

                <section className="panel stack panelLarge">
                  <div className="panelHeading">
                    <div>
                      <h2>最近对拍结果</h2>
                      <p className="muted">概览里只保留一份结果摘要，完整操作放到“对拍运行”。</p>
                    </div>
                  </div>
                  <DuelResultPanel
                    result={selectedProject?.last_duel_result ?? null}
                    onUseFailureInput={fillQuickInputFromFailure}
                  />
                </section>
              </section>
            </>
          ) : null}

          {workspaceTab === "edit" ? (
            <>
              <section className="twoCol">
                <section className="panel stack panelLarge">
                  <div className="panelHeading">
                    <div>
                      <h2>题面编辑</h2>
                      <p className="muted">只放题面相关按钮，保存和解析都在这里。</p>
                    </div>
                    <div className="editorActions">
                      <CopyButton text={problemText} label="复制题面" />
                      <button className="button secondary" onClick={() => void startParse()} disabled={busy || !selectedProjectId}>
                        解析题面
                      </button>
                      <button className="button" onClick={() => void saveProblem()} disabled={busy || !selectedProjectId}>
                        保存题面
                      </button>
                    </div>
                  </div>
                  <CodeEditor value={problemText} language="markdown" onChange={setProblemText} height={520} />
                </section>

                <section className="panel stack panelLarge">
                  <div className="panelHeading">
                    <div>
                      <h2>用户代码</h2>
                      <p className="muted">当前编辑器里的代码就是保存和快速运行的来源。</p>
                    </div>
                    <div className="editorActions">
                      <CopyButton text={userCode} label="复制代码" />
                      <button className="button" onClick={() => void saveUserSolution()} disabled={busy || !selectedProjectId}>
                        保存用户代码
                      </button>
                    </div>
                  </div>
                  <CodeEditor value={userCode} language="cpp" onChange={setUserCode} height={520} />
                </section>
              </section>

              <section className="panel stack panelLarge">
                <div className="panelHeading">
                  <div>
                    <h2>快速运行</h2>
                    <p className="muted">调单组输入时留在编辑页，不用再切去找按钮。</p>
                  </div>
                  <div className="metaRow">
                    <label className="field compactField fieldShort">
                      <span className="fieldLabel">时限 ms</span>
                      <input
                        className="input"
                        value={quickRunTimeLimitMs}
                        onChange={(event) => setQuickRunTimeLimitMs(event.target.value)}
                      />
                    </label>
                    <button
                      className="button ghost"
                      onClick={fillQuickInputFromFailure}
                      disabled={busy || !selectedProject?.last_duel_result?.failure?.input}
                    >
                      回填反例输入
                    </button>
                    <button
                      className="button secondary"
                      onClick={() => void runQuickUserCode()}
                      disabled={busy || !selectedProjectId}
                    >
                      运行当前代码
                    </button>
                  </div>
                </div>
                <QuickRunPanel
                  input={quickInput}
                  onInputChange={setQuickInput}
                  result={quickRunResult}
                />
              </section>
            </>
          ) : null}

          {workspaceTab === "assets" ? (
            <>
              <section className="twoCol">
                <section className="panel stack panelLarge">
                  <div className="panelHeading">
                    <div>
                      <h2>生成控制</h2>
                      <p className="muted">生成参数和按钮集中在这里，避免和编辑、对拍动作混在一起。</p>
                    </div>
                    <button
                      className="button"
                      onClick={() => void startGenerate()}
                      disabled={busy || !selectedProjectId}
                    >
                      开始生成
                    </button>
                  </div>
                  <div className="formGrid">
                    <label className="field">
                      <span className="fieldLabel">生成器</span>
                      <select className="select" value={provider} onChange={(event) => setProvider(event.target.value)}>
                        <option value="auto">auto</option>
                        <option value="template">template</option>
                        <option value="openai">openai</option>
                      </select>
                    </label>
                    <label className="field">
                      <span className="fieldLabel">回修轮数</span>
                      <input
                        className="input"
                        value={repairRounds}
                        onChange={(event) => setRepairRounds(event.target.value)}
                      />
                    </label>
                  </div>
                  <label className="toggleField">
                    <input
                      type="checkbox"
                      checked={selfTest}
                      onChange={(event) => setSelfTest(event.target.checked)}
                    />
                    <span>生成后自检</span>
                  </label>
                  <div className="muted">
                    当前产物数：{Object.keys(selectedProject?.artifacts ?? {}).length}；OpenAI：
                    {runtime?.openai.provider_available ? "已就绪" : "未就绪"}
                  </div>
                </section>
                <TaskPanel task={task} />
              </section>

              <section className="panel stack panelLarge">
                <div className="panelHeading">
                  <div>
                    <h2>生成产物</h2>
                    <p className="muted">只在这个工作区预览产物，减少整页来回滚动。</p>
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
                    <h2>ProblemSpec 编辑</h2>
                    <p className="muted">结构化题面和生成资产是同一个阶段，所以放在一起。</p>
                  </div>
                  {selectedProject ? (
                    <StatusBadge label={selectedProject.status} tone={getStatusTone(selectedProject.status)} />
                  ) : null}
                </div>
                {selectedProject ? (
                  <ProblemSpecEditor
                    value={specDraft}
                    busy={busy}
                    disabled={!selectedProjectId}
                    onChange={setSpecDraft}
                    onSave={() => void saveProblemSpec()}
                    onReset={() => setSpecDraft(cloneProblemSpec(selectedProject.problem_spec))}
                  />
                ) : (
                  <div className="emptyState">请选择项目。</div>
                )}
              </section>
            </>
          ) : null}

          {workspaceTab === "run" ? (
            <>
              <section className="twoCol">
                <section className="panel stack panelLarge">
                  <div className="panelHeading">
                    <div>
                      <h2>对拍控制</h2>
                      <p className="muted">对拍参数和启动按钮放到独立区域，不再和生成按钮混在一起。</p>
                    </div>
                    <button
                      className="button"
                      onClick={() => void startDuel()}
                      disabled={busy || !selectedProjectId}
                    >
                      开始对拍
                    </button>
                  </div>
                  <div className="formGrid">
                    <label className="field">
                      <span className="fieldLabel">轮数</span>
                      <input
                        className="input"
                        value={duelRounds}
                        onChange={(event) => setDuelRounds(event.target.value)}
                      />
                    </label>
                    <div className="infoItem">
                      <div className="infoLabel">失败输入</div>
                      <div className="infoValue">
                        {selectedProject?.last_duel_result?.failure?.input ? "可回填到快测" : "暂无"}
                      </div>
                    </div>
                  </div>
                  <div className="editorActions">
                    <button
                      className="button secondary"
                      onClick={fillQuickInputFromFailure}
                      disabled={busy || !selectedProject?.last_duel_result?.failure?.input}
                    >
                      失败输入回填到快测
                    </button>
                    <button
                      className="button ghost"
                      onClick={() => setWorkspaceTab("edit")}
                      disabled={!selectedProjectId}
                    >
                      去编辑 / 快测
                    </button>
                  </div>
                </section>

                <TaskPanel task={task} />
              </section>

              <section className="panel stack panelLarge">
                <div className="panelHeading">
                  <div>
                    <h2>对拍结果</h2>
                    <p className="muted">对拍相关信息只留在这个工作区，避免概览和编辑页信息过载。</p>
                  </div>
                </div>
                <DuelResultPanel
                  result={selectedProject?.last_duel_result ?? null}
                  onUseFailureInput={fillQuickInputFromFailure}
                />
              </section>
            </>
          ) : null}
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

function WorkspaceTabs({
  active,
  onChange,
}: {
  active: WorkspaceTab;
  onChange: (tab: WorkspaceTab) => void;
}) {
  const tabs: Array<{ id: WorkspaceTab; label: string; hint: string }> = [
    { id: "overview", label: "概览", hint: "状态 / 最近结果" },
    { id: "edit", label: "编辑", hint: "题面 / 代码 / 快测" },
    { id: "assets", label: "生成资产", hint: "生成 / Spec / 产物" },
    { id: "run", label: "对拍运行", hint: "对拍 / 日志 / 结果" },
  ];

  return (
    <section className="panel workspaceTabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`workspaceTab ${active === tab.id ? "active" : ""}`}
          onClick={() => onChange(tab.id)}
        >
          <span className="workspaceTabLabel">{tab.label}</span>
          <span className="workspaceTabHint">{tab.hint}</span>
        </button>
      ))}
    </section>
  );
}

function TaskPanel({ task }: { task: TaskRecord | null }) {
  return (
    <section className="panel stack panelLarge">
      <div className="panelHeading">
        <div>
          <h2>当前任务</h2>
          <p className="muted">异步任务状态、阶段和日志。</p>
        </div>
        {task ? (
          <StatusBadge label={`${task.status} · ${task.progress}%`} tone={getStatusTone(task.status)} />
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
        <div className="emptyState">还没有任务。解析 / 生成 / 对拍后，这里会显示进度和日志。</div>
      )}
    </section>
  );
}

function ProjectSummaryPanel({
  project,
  onOpenEdit,
  onOpenAssets,
  onOpenRun,
}: {
  project: ProjectRecord | null;
  onOpenEdit: () => void;
  onOpenAssets: () => void;
  onOpenRun: () => void;
}) {
  if (!project) {
    return (
      <section className="panel stack panelLarge">
        <div className="panelHeading">
          <div>
            <h2>项目概览</h2>
            <p className="muted">先从左侧选择项目。</p>
          </div>
        </div>
        <div className="emptyState">当前没有选中的项目。</div>
      </section>
    );
  }

  return (
    <section className="panel stack panelLarge">
      <div className="panelHeading">
        <div>
          <h2>项目概览</h2>
          <p className="muted">把最常看的项目信息集中到一张卡里。</p>
        </div>
        <StatusBadge label={project.status} tone={getStatusTone(project.status)} />
      </div>

      <div className="cardGrid">
        <InfoItem label="project" value={project.name} />
        <InfoItem label="artifacts" value={String(Object.keys(project.artifacts ?? {}).length)} />
        <InfoItem label="samples" value={String(project.problem_spec?.samples?.length ?? 0)} />
        <InfoItem label="updated" value={formatTime(project.updated_at)} />
      </div>

      <div className="subtleCard stack">
        <div className="infoLabel">ProblemSpec</div>
        <div className="infoValue">{project.problem_spec?.title ?? "尚未解析"}</div>
        <div className="muted">
          题型：{project.problem_spec?.problem_type_guess?.slice(0, 3).join(" / ") || "未识别"}
        </div>
      </div>

      <div className="editorActions">
        <button type="button" className="button secondary" onClick={onOpenEdit}>
          去编辑
        </button>
        <button type="button" className="button secondary" onClick={onOpenAssets}>
          去生成资产
        </button>
        <button type="button" className="button secondary" onClick={onOpenRun}>
          去对拍运行
        </button>
      </div>
    </section>
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
      {artifact ? (
        <div className="stack">
          <div className="metaRow">
            <StatusBadge label={artifact.type} tone="neutral" />
            <StatusBadge label={artifact.language} tone="neutral" />
            <CopyButton text={artifact.code} label="复制产物" />
          </div>
          <CodeEditor
            value={artifact.code}
            language={toEditorLanguage(artifact.language, artifact.type)}
            readOnly
            height={420}
          />
        </div>
      ) : (
        <div className="emptyState">当前没有可预览的产物。</div>
      )}
    </div>
  );
}

function QuickRunPanel({
  input,
  onInputChange,
  result,
}: {
  input: string;
  onInputChange: (value: string) => void;
  result: QuickRunResult | null;
}) {
  return (
    <div className="stack">
      <div className="editorHeader">
        <div>
          <h3>测试输入</h3>
          <div className="muted">这里可以粘贴样例、反例或你手工构造的数据。</div>
        </div>
        <div className="editorActions">
          <CopyButton text={input} label="复制输入" />
        </div>
      </div>
      <CodeEditor value={input} language="plaintext" onChange={onInputChange} height={180} />

      {result ? (
        <div className="stack">
          <div className="metaRow">
            <StatusBadge
              label={result.compile_ok ? "编译成功" : "编译失败"}
              tone={result.compile_ok ? "success" : "error"}
            />
            <StatusBadge
              label={result.timed_out ? "运行超时" : `exit ${result.exit_code ?? "-"}`}
              tone={result.timed_out ? "warning" : result.compile_ok ? "neutral" : "error"}
            />
            <StatusBadge label={`${result.time_ms} ms`} tone="neutral" />
          </div>

          <div className="quickRunGrid">
            <section className="stack">
              <div className="sectionHeader">
                <h3>stdout</h3>
                <CopyButton text={result.stdout} label="复制 stdout" />
              </div>
              <CodeEditor
                value={result.stdout || "(empty)"}
                language="plaintext"
                readOnly
                height={180}
              />
            </section>
            <section className="stack">
              <div className="sectionHeader">
                <h3>stderr</h3>
                <CopyButton text={result.stderr} label="复制 stderr" />
              </div>
              <CodeEditor
                value={result.stderr || "(empty)"}
                language="plaintext"
                readOnly
                height={180}
              />
            </section>
          </div>

          <section className="stack">
            <div className="sectionHeader">
              <h3>编译日志</h3>
              <CopyButton text={result.compile_log} label="复制编译日志" />
            </div>
            <CodeEditor
              value={result.compile_log || "(empty)"}
              language="plaintext"
              readOnly
              height={160}
            />
          </section>
        </div>
      ) : (
        <div className="emptyState">还没有运行结果。填入输入后点“运行当前代码”。</div>
      )}
    </div>
  );
}

function DuelResultPanel({
  result,
  onUseFailureInput,
}: {
  result: DuelResult | null;
  onUseFailureInput?: () => void;
}) {
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
            {failure.stderr ? (
              <div className="stack">
                <div className="metaRow">
                  <div className="pill">stderr</div>
                  <CopyButton text={failure.stderr} label="复制 stderr" />
                </div>
                <CodeEditor value={failure.stderr} language="plaintext" readOnly height={160} />
              </div>
            ) : null}
          </div>
          <div className="stack">
            <div className="sectionHeader">
              <h3>输入</h3>
              <div className="inlineActions">
                <CopyButton text={failure.input || ""} label="复制输入" />
                {onUseFailureInput ? (
                  <button type="button" className="button secondary buttonSmall" onClick={onUseFailureInput}>
                    回填到快测
                  </button>
                ) : null}
              </div>
            </div>
            <CodeEditor value={failure.input || "(empty)"} language="plaintext" readOnly height={180} />
          </div>
          <DiffViewer expected={failure.expected_output} actual={failure.actual_output} />
          {Object.keys(result.compile_logs).length > 0 ? (
            <div className="stack">
              <h3>编译日志</h3>
              {Object.entries(result.compile_logs).map(([name, log]) => (
                <div key={name} className="stack">
                  <div className="metaRow">
                    <div className="pill">{name}</div>
                    <CopyButton text={log || ""} label="复制日志" />
                  </div>
                  <CodeEditor value={log || "(empty)"} language="plaintext" readOnly height={180} />
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
      <div className="sectionHeader">
        <h3>输出对比</h3>
        <div className="inlineActions">
          <CopyButton text={expected} label="复制 expected" />
          <CopyButton text={actual} label="复制 actual" />
        </div>
      </div>
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

function emptyProblemSpec(): ProblemSpec {
  return {
    title: "Untitled Problem",
    statement: "",
    input_format: "",
    output_format: "",
    constraints: {},
    samples: [],
    problem_type_guess: [],
    special_notes: [],
    parse_confidence: {},
  };
}

function cloneProblemSpec(spec?: ProblemSpec | null): ProblemSpec {
  const base = spec ?? emptyProblemSpec();
  return {
    title: base.title ?? "Untitled Problem",
    statement: base.statement ?? "",
    input_format: base.input_format ?? "",
    output_format: base.output_format ?? "",
    constraints: { ...(base.constraints ?? {}) },
    samples: (base.samples ?? []).map((sample) => ({
      input: sample.input ?? "",
      output: sample.output ?? "",
    })),
    problem_type_guess: [...(base.problem_type_guess ?? [])],
    special_notes: [...(base.special_notes ?? [])],
    parse_confidence: { ...(base.parse_confidence ?? {}) },
  };
}

function clampInt(value: string, fallback: number, min: number, max: number): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, parsed));
}

function toEditorLanguage(language: string, artifactType?: string): string {
  const normalized = language.toLowerCase();
  if (normalized === "cpp" || normalized === "c++") {
    return "cpp";
  }
  if (normalized === "py" || normalized === "python") {
    return "python";
  }
  if (normalized === "md" || normalized === "markdown") {
    return "markdown";
  }
  if (normalized === "json") {
    return "json";
  }
  if (artifactType === "readme") {
    return "markdown";
  }
  if (artifactType === "compare") {
    return "python";
  }
  return "plaintext";
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
