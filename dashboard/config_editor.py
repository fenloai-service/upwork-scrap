"""Config editor utilities for the Streamlit dashboard.

Saves settings to the database (settings table). Falls back to YAML files
on disk when the database is unavailable or the setting hasn't been stored yet.
"""

import logging
import shutil

import yaml

import config

log = logging.getLogger(__name__)


def _config_key(filename: str) -> str:
    """Convert a YAML filename to a settings DB key ('ai_models.yaml' -> 'ai_models')."""
    return filename.replace(".yaml", "")


def load_yaml_config(filename: str) -> dict:
    """Load a config — tries DB first, falls back to YAML file.

    Args:
        filename: Name of the file in config/ directory (e.g., "ai_models.yaml").

    Returns:
        Parsed dict, or empty dict if not found anywhere.
    """
    # Try database first
    try:
        import database.db as _db_mod
        db_data = _db_mod.get_setting(_config_key(filename))
        if db_data is not None:
            return db_data
    except Exception as e:
        log.debug(f"DB lookup failed for {filename}, falling back to YAML: {e}")

    # Fall back to YAML file on disk
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
    """Save config to the database. Also writes YAML file as backup.

    Args:
        filename: Name of the file in config/ directory.
        data: Dict to save.

    Returns:
        True if saved successfully, False otherwise.
    """
    # Save to database (primary storage)
    try:
        import database.db as _db_mod
        key = _config_key(filename)
        if _db_mod.save_setting(key, data):
            log.info(f"Config saved to DB: {filename}")
            # Also write YAML as local backup (best-effort)
            _write_yaml_backup(filename, data)
            return True
        else:
            log.warning(f"save_setting returned False for {filename}")
    except Exception as e:
        log.warning(f"DB save failed for {filename}, falling back to YAML: {e}")

    # Fall back to YAML-only save
    return _write_yaml_backup(filename, data)


def _write_yaml_backup(filename: str, data: dict) -> bool:
    """Write data to YAML file with .bak backup (best-effort local copy)."""
    filepath = config.CONFIG_DIR / filename
    backup_path = filepath.with_suffix(filepath.suffix + ".bak")

    try:
        if filepath.exists():
            shutil.copy2(filepath, backup_path)

        tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        tmp_path.replace(filepath)
        return True
    except Exception as e:
        log.debug(f"YAML backup write failed for {filename}: {e}")
        if backup_path.exists() and not filepath.exists():
            shutil.copy2(backup_path, filepath)
        return False


def get_config_files() -> list[dict]:
    """List all config files with their metadata.

    Returns:
        List of dicts with 'filename', 'path', 'exists' keys.
        'exists' is True if the config is in the DB or on disk.
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

    # Check which keys exist in DB
    db_keys = set()
    try:
        import database.db as _db_mod
        db_keys = set(_db_mod.get_all_settings().keys())
    except Exception:
        pass

    result = []
    for filename in known_configs:
        filepath = config.CONFIG_DIR / filename
        result.append({
            "filename": filename,
            "path": str(filepath),
            "exists": _config_key(filename) in db_keys or filepath.exists(),
        })

    return result
