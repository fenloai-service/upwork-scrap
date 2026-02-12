"""YAML config editor utilities for the Streamlit dashboard.

Provides load/save/backup functions for editing config files from the dashboard.
"""

import os
import shutil
import logging
from pathlib import Path

import yaml

import config

log = logging.getLogger(__name__)


def load_yaml_config(filename: str) -> dict:
    """Load a YAML config file.

    Args:
        filename: Name of the file in config/ directory (e.g., "ai_models.yaml").

    Returns:
        Parsed YAML dict, or empty dict if file not found.
    """
    filepath = config.CONFIG_DIR / filename
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
        return data if data is not None else {}
    except FileNotFoundError:
        log.warning(f"Config file not found: {filepath}")
        return {}
    except yaml.YAMLError as e:
        log.error(f"Failed to parse {filepath}: {e}")
        return {}


def save_yaml_config(filename: str, data: dict) -> bool:
    """Save data to a YAML config file with .bak backup.

    Creates a backup of the existing file before overwriting.
    Uses atomic write (write to temp, then rename) for safety.

    Args:
        filename: Name of the file in config/ directory.
        data: Dict to serialize as YAML.

    Returns:
        True if saved successfully, False otherwise.
    """
    filepath = config.CONFIG_DIR / filename
    backup_path = filepath.with_suffix(filepath.suffix + ".bak")

    try:
        # Create backup if file exists
        if filepath.exists():
            shutil.copy2(filepath, backup_path)

        # Write to temp file first, then rename (atomic on same filesystem)
        tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # Atomic rename
        tmp_path.replace(filepath)

        log.info(f"Config saved: {filename}")
        return True

    except Exception as e:
        log.error(f"Failed to save {filename}: {e}")
        # Try to restore backup if write failed
        if backup_path.exists() and not filepath.exists():
            shutil.copy2(backup_path, filepath)
        return False


def get_config_files() -> list[dict]:
    """List all YAML config files with their metadata.

    Returns:
        List of dicts with 'filename', 'path', 'exists' keys.
    """
    known_configs = [
        "ai_models.yaml",
        "scraping.yaml",
        "user_profile.yaml",
        "projects.yaml",
        "proposal_guidelines.yaml",
        "job_preferences.yaml",
        "email_config.yaml",
    ]

    result = []
    for filename in known_configs:
        filepath = config.CONFIG_DIR / filename
        result.append({
            "filename": filename,
            "path": str(filepath),
            "exists": filepath.exists(),
        })

    return result
