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
