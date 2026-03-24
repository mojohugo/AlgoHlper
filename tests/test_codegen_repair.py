import json
import sys
import types

from algohlper.config import Settings
from algohlper.models import GenerationRequest, ProblemSample, ProblemSpec, ProjectRecord
from algohlper.services.codegen import OpenAICodeGenerator


def test_openai_codegen_repairs_failed_generation(monkeypatch, tmp_path) -> None:
    broken_payload = {
        "brute_cpp": r"""
#include <bits/stdc++.h>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    long long a, b;
    if (!(cin >> a >> b)) return 0;
    cout << a + b << "\n";
    return 0;
}
""",
        "generator_cpp": "int main( { return 0; }",
        "notes": "first try",
    }
    fixed_payload = {
        "brute_cpp": broken_payload["brute_cpp"],
        "generator_cpp": r"""
#include <bits/stdc++.h>
using namespace std;
int main(int argc, char** argv) {
    long long seed = argc > 1 ? atoll(argv[1]) : 1;
    string mode = argc > 2 ? argv[2] : "small";
    int size = argc > 3 ? atoi(argv[3]) : 3;
    (void)seed;
    (void)mode;
    cout << size << ' ' << 1 << "\n";
    return 0;
}
""",
        "notes": "repaired",
    }

    calls: list[dict] = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            payload = broken_payload if len(calls) == 1 else fixed_payload
            return types.SimpleNamespace(output_text=__import__("json").dumps(payload, ensure_ascii=False))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    settings = Settings(data_dir=tmp_path, cxx="g++", openai_api_key="test-key")
    generator = OpenAICodeGenerator(settings)
    spec = ProblemSpec(
        title="A+B",
        samples=[ProblemSample(input="1 2\n", output="3\n")],
    )
    project = ProjectRecord(
        id="prj_test",
        name="repair-demo",
        raw_problem_content="# A+B\n",
        problem_spec=spec,
    )

    result = generator.generate(
        project=project,
        spec=spec,
        request=GenerationRequest(provider="openai", repair_rounds=1, self_test=True),
    )

    assert result.provider == "openai"
    assert result.validation.generator_smoke_ok is True
    assert result.validation.sample_passed == 1
    assert len(calls) == 2
    assert "generator" in result.artifacts


def test_openai_codegen_accepts_sse_string_response(monkeypatch, tmp_path) -> None:
    payload = {
        "brute_cpp": "int main() { return 0; }",
        "generator_cpp": "int main(int argc, char** argv) { return argc > 10 ? 1 : 0; }",
        "notes": "streamed",
    }
    payload_text = json.dumps(payload, ensure_ascii=False)
    sse_response = (
        "event: response.created\n"
        'data: {"type":"response.created","response":{"id":"resp_1","output":[]}}\n\n'
        "event: response.output_text.done\n"
        f"data: {json.dumps({'type': 'response.output_text.done', 'text': payload_text}, ensure_ascii=False)}\n\n"
        "event: response.completed\n"
        f"data: {json.dumps({'type': 'response.completed', 'response': {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': payload_text}]}]}}, ensure_ascii=False)}\n\n"
    )

    calls: list[dict] = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return sse_response

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))

    settings = Settings(data_dir=tmp_path, openai_api_key="test-key")
    generator = OpenAICodeGenerator(settings)
    spec = ProblemSpec(title="SSE Demo")
    project = ProjectRecord(
        id="prj_sse",
        name="sse-demo",
        raw_problem_content="# SSE Demo\n",
        problem_spec=spec,
    )

    result = generator.generate(
        project=project,
        spec=spec,
        request=GenerationRequest(provider="openai", self_test=False),
    )

    assert result.provider == "openai"
    assert result.artifacts["brute"].code == payload["brute_cpp"]
    assert result.artifacts["generator"].code == payload["generator_cpp"]
    assert any("streamed" in warning for warning in result.warnings)
    assert result.validation.skipped is True
    assert calls[0]["text"]["format"]["type"] == "json_schema"
    assert calls[0]["input"][0]["role"] == "developer"
    assert calls[0]["input"][1]["role"] == "user"
