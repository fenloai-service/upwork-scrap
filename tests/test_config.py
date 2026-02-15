"""Tests for YAML config loading and validation.

These tests validate that config files parse correctly and that
missing required fields produce clear errors.

Run: pytest tests/test_config.py -v
"""
import os

import pytest


REQUIRED_CONFIGS = {
    "job_preferences.yaml": "preferences",
    "user_profile.yaml": "profile",
    "projects.yaml": "projects",
    "proposal_guidelines.yaml": "guidelines",
    "email_config.yaml": "email",
}


def test_all_yaml_configs_parse():
    """Each config/*.yaml file should parse with yaml.safe_load() without error."""
    import yaml

    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

    if not os.path.isdir(config_dir):
        pytest.skip("config/ directory not yet created (Step 1.1)")

    for filename, expected_key in REQUIRED_CONFIGS.items():
        filepath = os.path.join(config_dir, filename)
        if not os.path.exists(filepath):
            pytest.skip(f"{filename} not yet created (Step 1.1)")

        with open(filepath) as f:
            data = yaml.safe_load(f)

        assert data is not None, f"{filename} parsed as None"
        assert expected_key in data, (
            f"{filename} missing required top-level key '{expected_key}'. "
            f"Found keys: {list(data.keys())}"
        )


def test_missing_required_config_field_raises(tmp_path, monkeypatch):
    """Preferences without 'match_threshold' should raise KeyError with helpful message."""
    import yaml
    from unittest.mock import patch

    # Write a preferences file missing match_threshold
    bad_prefs = {
        "preferences": {
            "categories": ["RAG / Document AI"],
            "required_skills": ["Python"],
            "nice_to_have_skills": [],
            "budget": {"fixed_min": 1000, "fixed_max": 10000, "hourly_min": 40},
            "client_criteria": {"payment_verified": True},
            "exclusions": {"keywords": []},
            # match_threshold intentionally missing
        }
    }
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    prefs_path = config_dir / "job_preferences.yaml"
    with open(prefs_path, "w") as f:
        yaml.dump(bad_prefs, f)

    # Patch CONFIG_DIR to use our temp path
    import config
    import config_loader
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_loader, "_CONFIG_DIR", config_dir)

    try:
        from matcher import load_preferences

        # Also bypass DB lookup so the test YAML is actually used
        with patch("database.db.load_config_from_db", return_value=None):
            with pytest.raises(KeyError):
                load_preferences()  # Takes no arguments, reads from CONFIG_DIR
    except ImportError:
        pytest.skip("matcher.py not yet created (Step 1.3)")


def test_partial_config_with_missing_files():
    """When some config files are missing, loader should raise ConfigError with clear message."""
    import tempfile
    import os
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create only some config files, not all
        config_dir = os.path.join(tmpdir, "config")
        os.makedirs(config_dir, exist_ok=True)

        # Create only job_preferences.yaml, omit others
        import yaml
        prefs = {
            "preferences": {
                "categories": ["AI"],
                "required_skills": ["Python"],
                "nice_to_have_skills": [],
                "budget": {"fixed_min": 1000, "fixed_max": 10000, "hourly_min": 40},
                "client_criteria": {"payment_verified": True, "min_total_spent": 5000, "min_rating": 4.5},
                "exclusions": {"keywords": []},
                "match_threshold": 70
            }
        }
        with open(os.path.join(config_dir, "job_preferences.yaml"), "w") as f:
            yaml.dump(prefs, f)

        # Try to load a missing config
        try:
            from proposal_generator import load_config_file
            from config_loader import ConfigError
            import config as main_config

            # Temporarily override CONFIG_DIR
            from pathlib import Path
            original_config_dir = main_config.CONFIG_DIR
            main_config.CONFIG_DIR = Path(tmpdir) / "config"

            try:
                # Bypass DB so the missing YAML file actually triggers the error
                with patch("database.db.load_config_from_db", return_value=None):
                    with pytest.raises(ConfigError):
                        load_config_file("user_profile.yaml")  # This file doesn't exist
            finally:
                main_config.CONFIG_DIR = original_config_dir

        except ImportError:
            pytest.skip("proposal_generator.py not yet created (Step 1.4)")
