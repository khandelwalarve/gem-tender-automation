"""
Loads config/settings.yaml (or settings.example.yaml as a fallback for local
dev/testing) into a single dict accessible from any module.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


@lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    real = _CONFIG_DIR / "settings.yaml"
    example = _CONFIG_DIR / "settings.example.yaml"

    path = real if real.exists() else example
    if not path.exists():
        raise FileNotFoundError(
            f"No settings file found at {real} or {example}. "
            "Copy settings.example.yaml to settings.yaml and fill in real values."
        )

    with open(path) as f:
        settings = yaml.safe_load(f)

    # Environment variables override file values for secrets (e.g. in CI/CD).
    if os.environ.get("DATABASE_URL"):
        settings.setdefault("database", {})["url"] = os.environ["DATABASE_URL"]

    return settings
