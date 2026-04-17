"""Configuration loader — charge le config.yaml du tenant actif."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def load_tenant_config(tenant_id: str) -> dict[str, Any]:
    """Charge la config d'un tenant depuis tenant-configs/tenant-{id}/config.yaml."""
    load_dotenv()

    base_path = Path(os.environ.get(
        "TENANT_CONFIGS_PATH",
        Path.home() / "jarvis-platform" / "tenant-configs"
    ))
    config_file = base_path / f"tenant-{tenant_id}" / "config.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"Config tenant introuvable : {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_personas(tenant_id: str) -> dict[str, Any]:
    """Charge les personas narratives d'un tenant."""
    base_path = Path(os.environ.get(
        "TENANT_CONFIGS_PATH",
        Path.home() / "jarvis-platform" / "tenant-configs"
    ))
    personas_file = base_path / f"tenant-{tenant_id}" / "personas.yaml"

    if not personas_file.exists():
        return {}

    with open(personas_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
