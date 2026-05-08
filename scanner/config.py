"""Configuration loading for Batman Scanner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import toml

from scanner.models import ScanSettings


DEFAULT_CONFIG_PATH = "config.local.toml"


def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load local config if it exists, otherwise return empty sections."""
    config_path = Path(path)
    if not config_path.exists():
        return {"ibkr": {}, "scanner": {}}
    return toml.load(config_path)


def settings_from_config(config: dict[str, Any]) -> ScanSettings:
    scanner_config = config.get("scanner", {})
    return ScanSettings(**{key: value for key, value in scanner_config.items() if hasattr(ScanSettings, key)})


def ibkr_config(config: dict[str, Any]) -> dict[str, Any]:
    defaults = {"host": "127.0.0.1", "port": 7497, "client_id": 11}
    defaults.update(config.get("ibkr", {}))
    return defaults

