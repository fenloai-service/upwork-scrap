"""Centralized config loading — DB first, YAML fallback.

Single source of truth for config resolution. Only this module
should import ``database.db.load_config_from_db``.
"""

import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

# Derived independently to avoid circular imports with config.py
_CONFIG_DIR = Path(__file__).parent / "config"


class ConfigError(Exception):
    """Raised when a required config cannot be loaded from any source."""


def load_config(
    config_name: str,
    *,
    yaml_path: Path | None = None,
    required_keys: list[str] | None = None,
    top_level_key: str | None = None,
    default: dict | None = None,
    schema: dict[str, type] | None = None,
) -> dict:
    """Load config from DB first, falling back to YAML file.

    Args:
        config_name: Config key for DB lookup (e.g. ``"scraping"``).
        yaml_path: Full path to YAML fallback. Defaults to ``config/{config_name}.yaml``.
        required_keys: Keys that must exist in the result; raises :class:`ConfigError` if missing.
        top_level_key: Extract this key from loaded data (e.g. ``"preferences"``).
        default: Return this if both DB and YAML fail. ``None`` means raise.
        schema: Optional dict mapping key names to expected types for validation.

    Returns:
        Parsed config dict.

    Raises:
        ConfigError: If config cannot be loaded and *default* is ``None``.
    """
    data = None

    # Stage 1: Try database
    try:
        from database.db import load_config_from_db

        db_data = load_config_from_db(config_name)
        if db_data is not None:
            data = db_data
    except Exception as e:
        log.warning("DB config lookup failed for '%s': %s", config_name, e)

    # Stage 2: Try YAML file
    if data is None:
        if yaml_path is None:
            yaml_path = _CONFIG_DIR / f"{config_name}.yaml"
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            log.warning("Config file not found: %s", yaml_path)
        except yaml.YAMLError as e:
            log.warning("Invalid YAML in %s: %s", yaml_path, e)

    # Stage 3: Apply default or raise
    if data is None:
        if default is not None:
            log.warning("Config '%s' not found, using defaults", config_name)
            return default
        raise ConfigError(
            f"Config '{config_name}' not found in DB or at {yaml_path}"
        )

    # Extract top-level key if specified
    if top_level_key and isinstance(data, dict):
        data = data.get(top_level_key, data)

    # Validate required keys
    if required_keys and isinstance(data, dict):
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise ConfigError(
                f"Config '{config_name}' missing required keys: {missing}"
            )

    # Validate schema (key -> expected type)
    if schema and isinstance(data, dict):
        for key, expected_type in schema.items():
            if key in data and not isinstance(data[key], expected_type):
                raise ConfigError(
                    f"Config '{config_name}': key '{key}' expected "
                    f"{expected_type.__name__}, got {type(data[key]).__name__}"
                )

    return data
