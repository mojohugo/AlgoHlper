from algohlper.config import Settings
from algohlper.models import DuelRequest
from algohlper.services.duel import DuelService


def test_duel_engine_finds_counterexample(tmp_path) -> None:
    brute_code = r"""
#include <bits/stdc++.h>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int a, b;
    if (!(cin >> a >> b)) return 0;
    cout << max(a, b) << "\n";
    return 0;
}
"""
    generator_code = r"""
#include <bits/stdc++.h>
using namespace std;
int main(int argc, char** argv) {
    long long seed = argc > 1 ? atoll(argv[1]) : 1;
    string mode = argc > 2 ? argv[2] : "random";
    int size = argc > 3 ? atoi(argv[3]) : 5;
    mt19937 rng((unsigned)seed);
    int a = (int)(rng() % max(1, size + 1));
    int b = (int)(rng() % max(1, size + 1));
    if (mode == "edge") {
        a = size;
        b = 0;
    }
    cout << a << ' ' << b << "\n";
    return 0;
}
"""
    user_code = r"""
#include <bits/stdc++.h>
using namespace std;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int a, b;
    if (!(cin >> a >> b)) return 0;
    cout << min(a, b) << "\n";
    return 0;
}
"""
    service = DuelService(Settings(data_dir=tmp_path, cxx="g++"))
    result = service.duel(
        brute_code=brute_code,
        generator_code=generator_code,
        user_code=user_code,
        request=DuelRequest(rounds=12, generator_mode=["edge", "random"], seed_start=7),
    )
    assert result.status == "counterexample_found"
    assert result.failure is not None
    assert result.failure.reason in {"wrong_answer", "user_runtime_error", "user_timed_out"}
    assert result.failure.input.strip() != ""
