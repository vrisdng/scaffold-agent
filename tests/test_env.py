import os
from pathlib import Path

from maikit_core.env import load_env_file


def test_load_env_file_sets_values_without_overriding_existing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# local settings",
                "MAIKIT_USE_LLM=1",
                'OPENAI_API_KEY="sk-test value"',
                "export ANTHROPIC_API_KEY=anthropic-test",
                "EXISTING=from_file",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("EXISTING", "from_environment")

    loaded = load_env_file(env_path)

    assert loaded == ["MAIKIT_USE_LLM", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    assert os.environ["MAIKIT_USE_LLM"] == "1"
    assert os.environ["OPENAI_API_KEY"] == "sk-test value"
    assert os.environ["ANTHROPIC_API_KEY"] == "anthropic-test"
    assert os.environ["EXISTING"] == "from_environment"
