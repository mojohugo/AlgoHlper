from pathlib import Path

from algohlper.config import Settings
from algohlper.services.task_queue import InProcessTaskQueue, create_task_queue


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


def test_celery_backend_falls_back_to_inprocess_when_package_missing(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, task_queue_backend="celery")
    queue = create_task_queue(settings)
    assert isinstance(queue, InProcessTaskQueue)


def test_settings_builds_redis_urls_from_windows_style_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGOHLPER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALGOHLPER_REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("ALGOHLPER_REDIS_PORT", "6379")
    monkeypatch.setenv("ALGOHLPER_REDIS_PASSWORD", "123456")
    monkeypatch.delenv("ALGOHLPER_CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("ALGOHLPER_CELERY_RESULT_BACKEND", raising=False)
    settings = Settings.from_env()
    assert settings.celery_broker_url == "redis://:123456@127.0.0.1:6379/0"
    assert settings.celery_result_backend == "redis://:123456@127.0.0.1:6379/1"
