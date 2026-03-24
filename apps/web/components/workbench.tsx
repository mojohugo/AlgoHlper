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
  const [duelRounds, setDuelRounds] = useState("50");
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  useEffect(() => {
    void refreshProjects();
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
            self_test: true,
            repair_rounds: 1,
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
      <section className="header">
        <div>
          <h1>AlgoHlper Workbench</h1>
          <div className="muted">最小前端工作台：项目 → 题面 → 异步生成 → 用户代码 → 异步对拍</div>
        </div>
        <div className="status">API: {API_BASE_URL}</div>
      </section>

      {error ? <section className="panel error">错误：{error}</section> : null}

      <section className="layout">
        <aside className="panel stack">
          <h2>项目</h2>
          <input
            className="input"
            value={projectName}
            onChange={(event) => setProjectName(event.target.value)}
            placeholder="项目名"
          />
          <div className="buttonRow">
            <button className="button" onClick={() => void createProject()} disabled={busy}>
              新建项目
            </button>
            <button className="button secondary" onClick={() => void refreshProjects()} disabled={busy}>
              刷新
            </button>
          </div>

          <div className="projectList">
            {projects.map((project) => (
              <button
                key={project.id}
                type="button"
                className={`projectItem ${project.id === selectedProjectId ? "active" : ""}`}
                onClick={() => setSelectedProjectId(project.id)}
              >
                <div>{project.name}</div>
                <div className="muted">{project.id}</div>
                <div className="pill">status: {project.status}</div>
              </button>
            ))}
            {projects.length === 0 ? <div className="muted">还没有项目。</div> : null}
          </div>
        </aside>

        <section className="grid">
          <section className="panel stack">
            <h2>工作区</h2>
            <div className="buttonRow">
              <button className="button" onClick={() => void saveProblem()} disabled={busy || !selectedProjectId}>
                保存题面
              </button>
              <button className="button secondary" onClick={() => void startParse()} disabled={busy || !selectedProjectId}>
                异步解析
              </button>
              <select className="select" value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="auto">auto</option>
                <option value="template">template</option>
                <option value="openai">openai</option>
              </select>
              <button className="button secondary" onClick={() => void startGenerate()} disabled={busy || !selectedProjectId}>
                异步生成
              </button>
              <button className="button ghost" onClick={() => void saveUserSolution()} disabled={busy || !selectedProjectId}>
                保存用户代码
              </button>
              <input
                className="input"
                value={duelRounds}
                onChange={(event) => setDuelRounds(event.target.value)}
                style={{ maxWidth: 120 }}
              />
              <button className="button ghost" onClick={() => void startDuel()} disabled={busy || !selectedProjectId}>
                异步对拍
              </button>
            </div>
            <div className="twoCol">
              <div className="stack">
                <h3>题面</h3>
                <textarea className="textarea" value={problemText} onChange={(event) => setProblemText(event.target.value)} />
              </div>
              <div className="stack">
                <h3>用户代码</h3>
                <textarea className="textarea" value={userCode} onChange={(event) => setUserCode(event.target.value)} />
              </div>
            </div>
          </section>

          <section className="twoCol">
            <section className="panel stack">
              <h2>当前任务</h2>
              {task ? (
                <>
                  <div className="status">
                    {task.type} / {task.status} / {task.current_stage ?? "-"} / {task.progress}%
                  </div>
                  {task.error ? <div className="error">{task.error}</div> : null}
                  <div className="pre">
                    {task.logs.length > 0
                      ? task.logs.map((log) => `[${log.level}] ${log.message}`).join("\n")
                      : "暂无日志"}
                  </div>
                </>
              ) : (
                <div className="muted">还没有任务。</div>
              )}
            </section>

            <section className="panel stack">
              <h2>当前项目</h2>
              {selectedProject ? (
                <>
                  <div className="pill">{selectedProject.id}</div>
                  <div className="pill">status: {selectedProject.status}</div>
                  <div>Artifacts: {Object.keys(selectedProject.artifacts ?? {}).join(", ") || "无"}</div>
                  <div className="pre">
                    {selectedProject.problem_spec
                      ? JSON.stringify(selectedProject.problem_spec, null, 2)
                      : "ProblemSpec 尚未生成"}
                  </div>
                </>
              ) : (
                <div className="muted">请选择项目。</div>
              )}
            </section>
          </section>

          <section className="twoCol">
            <section className="panel stack">
              <h2>生成产物预览</h2>
              <ArtifactTabs
                project={selectedProject}
                activeArtifact={activeArtifact}
                onChange={setActiveArtifact}
              />
            </section>

            <section className="panel stack">
              <h2>对拍结果</h2>
              <DuelResultPanel result={selectedProject?.last_duel_result ?? null} />
            </section>
          </section>
        </section>
      </section>
    </main>
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
            {artifactName}
            <span className="muted">({value.language})</span>
          </button>
        ))}
      </div>
      <div className="code">{artifact?.code ?? "当前没有可预览的产物。"}</div>
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
      <div className="status">
        {result.status} / {result.rounds_completed} / {result.rounds_requested}
      </div>
      <div>{result.summary}</div>
      {result.warnings.length > 0 ? (
        <div className="stack">
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
            <div className="pill">失败样例</div>
            <div>reason: {humanizeReason(failure.reason)}</div>
            <div>
              round={failure.round} seed={failure.seed} mode={failure.mode} size={failure.size}
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
        <div className="success">本轮没有发现失败样例。</div>
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

function asErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
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
