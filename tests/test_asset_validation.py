from algohlper.config import Settings
from algohlper.models import ArtifactRecord, ProblemSample, ProblemSpec
from algohlper.services.asset_validation import AssetValidationService


def test_asset_validation_passes_compile_generator_and_samples(tmp_path) -> None:
    spec = ProblemSpec(
        title="A+B",
        samples=[ProblemSample(input="1 2\n", output="3\n")],
    )
    artifacts = {
        "brute": ArtifactRecord(
            type="brute",
            language="cpp",
            code=r"""
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
        ),
        "generator": ArtifactRecord(
            type="generator",
            language="cpp",
            code=r"""
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
        ),
    }
    service = AssetValidationService(Settings(data_dir=tmp_path, cxx="g++"))
    result = service.validate_cpp_assets(spec=spec, artifacts=artifacts)
    assert result.errors == []
    assert result.generator_smoke_ok is True
    assert result.sample_total == 1
    assert result.sample_passed == 1


def test_asset_validation_reports_compile_error(tmp_path) -> None:
    spec = ProblemSpec(title="Broken")
    artifacts = {
        "brute": ArtifactRecord(
            type="brute",
            language="cpp",
            code="int main( { return 0; }",
        )
    }
    service = AssetValidationService(Settings(data_dir=tmp_path, cxx="g++"))
    result = service.validate_cpp_assets(spec=spec, artifacts=artifacts)
    assert result.errors
    assert "brute.cpp 编译失败" in result.errors
