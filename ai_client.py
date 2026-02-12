"""Unified AI client factory supporting multiple providers with fallback.

Usage:
    from ai_client import get_client

    client, model_name, provider_name = get_client("classification")
    client, model_name, provider_name = get_client("proposal_generation")
"""

import os
import logging
from pathlib import Path

import yaml
from openai import OpenAI

import config

log = logging.getLogger(__name__)

_CONFIG_PATH = config.CONFIG_DIR / "ai_models.yaml"


def load_ai_config(config_path: Path = None) -> dict:
    """Load AI models configuration — tries DB first, falls back to YAML.

    Args:
        config_path: Override path for testing. Defaults to config/ai_models.yaml.

    Returns:
        Parsed YAML dict with 'ai_models' key.

    Raises:
        FileNotFoundError: If config file doesn't exist.
    """
    if config_path is None:
        try:
            from database.db import load_config_from_db
            db_data = load_config_from_db("ai_models")
            if db_data is not None:
                return db_data
        except Exception:
            pass

    path = config_path or _CONFIG_PATH
    with open(path) as f:
        data = yaml.safe_load(f)
    return data


def _build_client(provider_cfg: dict) -> tuple:
    """Build an OpenAI client from a provider config dict.

    Returns:
        Tuple of (OpenAI client, api_key_resolved).

    Raises:
        RuntimeError: If required API key is not set.
    """
    base_url = provider_cfg["base_url"]

    api_key = provider_cfg.get("api_key")
    api_key_env = provider_cfg.get("api_key_env")

    if api_key_env:
        env_key = os.environ.get(api_key_env)
        if env_key:
            api_key = env_key
        elif not api_key:
            raise RuntimeError(
                f"{api_key_env} environment variable is not set.\n"
                f"Set it: export {api_key_env}='your-key-here'"
            )

    if not api_key:
        api_key = "no-key"

    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, api_key


def get_client(purpose: str, config_path: Path = None, skip_health_check: bool = False) -> tuple:
    """Get a configured OpenAI-compatible client for the given purpose.

    Tries the primary provider first; if it fails a health check, falls back
    through the configured fallback chain.

    Args:
        purpose: Either "classification" or "proposal_generation".
        config_path: Override config path for testing.
        skip_health_check: If True, skip provider health check (useful for tests).

    Returns:
        Tuple of (OpenAI client, model_name, provider_name).

    Raises:
        RuntimeError: If no provider could be initialized.
    """
    cfg = load_ai_config(config_path)
    ai_cfg = cfg["ai_models"]

    selection = ai_cfg[purpose]
    providers_cfg = ai_cfg["providers"]

    # Build ordered list: primary + fallbacks
    candidates = [
        {"provider": selection["provider"], "model": selection["model"]}
    ]
    for fb in selection.get("fallback", []):
        candidates.append({"provider": fb["provider"], "model": fb["model"]})

    last_error = None
    for candidate in candidates:
        provider_name = candidate["provider"]
        model_name = candidate["model"]
        provider_cfg = providers_cfg[provider_name]

        try:
            client, _ = _build_client(provider_cfg)

            if not skip_health_check:
                # Quick health check: try listing models (timeout 5s)
                health = check_provider_health(provider_name, config_path)
                if not health["success"]:
                    log.warning(f"Provider {provider_name} health check failed: {health['message']}")
                    last_error = RuntimeError(health["message"])
                    continue

            log.info(f"AI client initialized: {provider_name}/{model_name} for {purpose}")
            return client, model_name, provider_name

        except RuntimeError as e:
            log.warning(f"Provider {provider_name} unavailable: {e}")
            last_error = e
            continue

    raise RuntimeError(
        f"No AI provider available for '{purpose}'. "
        f"Tried: {[c['provider'] for c in candidates]}. "
        f"Last error: {last_error}"
    )


def check_provider_health(provider_name: str, config_path: Path = None) -> dict:
    """Check if a provider is reachable (quick connectivity test).

    Args:
        provider_name: Provider key from config.
        config_path: Override config path for testing.

    Returns:
        Dict with 'success', 'provider', 'message' keys.
    """
    try:
        cfg = load_ai_config(config_path)
        ai_cfg = cfg["ai_models"]
        provider_cfg = ai_cfg["providers"][provider_name]

        client, _ = _build_client(provider_cfg)
        # Use a short timeout for health checks
        client = OpenAI(
            api_key=client.api_key,
            base_url=str(provider_cfg["base_url"]),
            timeout=5.0,
        )

        models = client.models.list()
        model_ids = [m.id for m in models.data[:5]]

        return {
            "success": True,
            "provider": provider_name,
            "message": f"Connected. Models: {', '.join(model_ids)}",
            "models": model_ids,
        }

    except Exception as e:
        return {
            "success": False,
            "provider": provider_name,
            "message": str(e),
            "models": [],
        }


def test_connection(provider_name: str = None, config_path: Path = None) -> dict:
    """Test connection to an AI provider.

    Args:
        provider_name: Provider to test. If None, tests the classification provider.
        config_path: Override config path for testing.

    Returns:
        Dict with 'success', 'provider', 'message' keys.
    """
    try:
        cfg = load_ai_config(config_path)
        ai_cfg = cfg["ai_models"]

        if provider_name is None:
            provider_name = ai_cfg["classification"]["provider"]

        return check_provider_health(provider_name, config_path)

    except Exception as e:
        return {
            "success": False,
            "provider": provider_name,
            "message": str(e),
        }


def list_available_models(provider_name: str = None, config_path: Path = None) -> list:
    """List available models for a provider from config.

    Args:
        provider_name: Provider name. If None, lists for classification provider.
        config_path: Override config path for testing.

    Returns:
        List of model name strings.
    """
    cfg = load_ai_config(config_path)
    ai_cfg = cfg["ai_models"]

    if provider_name is None:
        provider_name = ai_cfg["classification"]["provider"]

    provider_cfg = ai_cfg["providers"][provider_name]
    return provider_cfg.get("models", [])
