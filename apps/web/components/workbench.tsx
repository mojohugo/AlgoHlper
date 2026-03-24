"use client";

import { useEffect, useMemo, useState } from "react";

type ProjectRecord = {
  id: string;
  name: string;
  status: string;
  raw_problem_content?: string | null;
  problem_spec?: unknown;
  artifacts: Record<string, { type: string; language: string; code: string }>;
  last_duel_result?: unknown;
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
              <ArtifactPreview project={selectedProject} artifactName="brute" />
              <ArtifactPreview project={selectedProject} artifactName="generator" />
            </section>

            <section className="panel stack">
              <h2>对拍结果</h2>
              <div className="pre">
                {selectedProject?.last_duel_result
                  ? JSON.stringify(selectedProject.last_duel_result, null, 2)
                  : "还没有对拍结果"}
              </div>
            </section>
          </section>
        </section>
      </section>
    </main>
  );
}

function ArtifactPreview({
  project,
  artifactName,
}: {
  project: ProjectRecord | null;
  artifactName: string;
}) {
  const artifact = project?.artifacts?.[artifactName];
  return (
    <div className="stack">
      <div className="pill">{artifactName}</div>
      <div className="code">{artifact?.code ?? `${artifactName} 暂无内容`}</div>
    </div>
  );
}

function asErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
