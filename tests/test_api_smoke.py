import time

from fastapi.testclient import TestClient

from algohlper.api.app import create_app
from algohlper.config import Settings


def test_api_parse_and_generate_starter_artifacts(tmp_path) -> None:
    app = create_app(Settings(data_dir=tmp_path, cxx="g++"))
    client = TestClient(app)

    project = client.post("/api/projects", json={"name": "demo"}).json()
    project_id = project["id"]
    problem = """# Demo Problem

题目描述
给你一个整数 n，输出 n。

输入格式
```text
n
```

输出格式
```text
n
```

样例输入
```text
5
```

样例输出
```text
5
```
"""
    response = client.post(
        f"/api/projects/{project_id}/problem-text",
        json={"content": problem, "format": "markdown"},
    )
    assert response.status_code == 200

    parse_response = client.post(f"/api/projects/{project_id}/parse")
    assert parse_response.status_code == 200
    parsed = parse_response.json()
    assert parsed["problem_spec"]["title"] == "Demo Problem"

    starter_response = client.post(f"/api/projects/{project_id}/generate-starter-artifacts")
    assert starter_response.status_code == 200
    artifacts = starter_response.json()["artifacts"]
    assert "brute" in artifacts
    assert "generator" in artifacts
    assert "compare" in artifacts


def test_api_generate_artifacts_auto_falls_back_to_template(tmp_path) -> None:
    app = create_app(Settings(data_dir=tmp_path, cxx="g++"))
    client = TestClient(app)

    project = client.post("/api/projects", json={"name": "demo-auto"}).json()
    project_id = project["id"]
    problem = """# Sum Problem

题目描述
给定两个整数，输出较大值。

输入格式
```text
a b
```

输出格式
```text
max(a, b)
```
"""
    client.post(
        f"/api/projects/{project_id}/problem-text",
        json={"content": problem, "format": "markdown"},
    )
    response = client.post(
        f"/api/projects/{project_id}/generate-artifacts",
        json={"provider": "auto"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "template"
    assert "brute" in payload["artifacts"]
    assert payload["warnings"]
    assert payload["validation"]["skipped"] is True


def test_api_async_generate_task_completes(tmp_path) -> None:
    app = create_app(Settings(data_dir=tmp_path, cxx="g++"))
    client = TestClient(app)

    project = client.post("/api/projects", json={"name": "demo-async"}).json()
    project_id = project["id"]
    problem = """# Async Problem

题目描述
输出输入值。

输入格式
```text
n
```

输出格式
```text
n
```
"""
    client.post(
        f"/api/projects/{project_id}/problem-text",
        json={"content": problem, "format": "markdown"},
    )
    response = client.post(
        f"/api/projects/{project_id}/generate-artifacts-async",
        json={"provider": "template"},
    )
    assert response.status_code == 200
    task_id = response.json()["task"]["id"]

    for _ in range(30):
        task_response = client.get(f"/api/tasks/{task_id}")
        task = task_response.json()
        if task["status"] in {"completed", "failed"}:
            break
        time.sleep(0.1)
    assert task["status"] == "completed"
