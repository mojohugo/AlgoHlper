from pathlib import Path

from algohlper.config import Settings


def test_settings_accepts_codex_api_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CODEX_API_KEY", "codex-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ALGOHLPER_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ALGOHLPER_DATA_DIR", str(tmp_path))
    settings = Settings.from_env()
    assert settings.openai_api_key == "codex-key"


def test_settings_reads_codex_config(monkeypatch, tmp_path) -> None:
    home_dir = tmp_path / "home"
    codex_dir = home_dir / ".codex"
    codex_dir.mkdir(parents=True)
    (codex_dir / "config.toml").write_text(
        """
model_provider = "codex"
model = "gpt-5.4"
model_reasoning_effort = "xhigh"

[model_providers.codex]
base_url = "https://example.invalid/codex"
env_key = "CODEX_API_KEY"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home_dir)
    monkeypatch.setenv("CODEX_API_KEY", "codex-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ALGOHLPER_OPENAI_API_KEY", raising=False)
    settings = Settings.from_env()
    assert settings.openai_api_key == "codex-key"
    assert settings.openai_base_url == "https://example.invalid/codex"
    assert settings.openai_model == "gpt-5.4"
    assert settings.openai_reasoning_effort == "xhigh"
