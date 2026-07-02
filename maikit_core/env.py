"""Small .env loader for local MaiKit runs."""

from __future__ import annotations

import os
import shlex
from pathlib import Path


def load_env_file(path: Path, override: bool = False) -> list[str]:
    """Loads KEY=VALUE pairs from a .env file.

    The loader intentionally supports the common local MVP subset: comments,
    blank lines, optional `export`, unquoted values, and shell-style quoted
    values. Existing environment variables win unless override is true.

    Args:
        path: Path to the .env file.
        override: Whether file values should replace existing environment
            variables.

    Returns:
        The names of variables loaded into os.environ.
    """
    if not path.exists():
        return []

    loaded: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if not override and key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded


def load_default_env_files(base_dir: Path | None = None) -> list[str]:
    """Loads the project-level .env file from the current working directory."""
    root = base_dir or Path.cwd()
    return load_env_file(root / ".env")


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()
    if "=" not in stripped:
        return None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
        return None

    value = raw_value.strip()
    if value and value[0] in {"'", '"'}:
        try:
            parts = shlex.split(value, comments=False, posix=True)
        except ValueError:
            return key, value.strip("'\"")
        return key, parts[0] if parts else ""

    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return key, value
