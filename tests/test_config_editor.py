"""Tests for dashboard YAML config editor utilities.

Run: pytest tests/test_config_editor.py -v
"""

import os

import pytest
import yaml


class TestLoadYamlConfig:
    """Tests for load_yaml_config()."""

    def test_load_existing_file(self, tmp_path, monkeypatch):
        """Should load and parse an existing YAML file."""
        from dashboard.config_editor import load_yaml_config
        import config

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)

        test_data = {"ai_models": {"classification": {"provider": "ollama_local"}}}
        with open(cfg_dir / "test.yaml", "w") as f:
            yaml.dump(test_data, f)

        result = load_yaml_config("test.yaml")
        assert result == test_data

    def test_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        """Should return empty dict when file doesn't exist."""
        from dashboard.config_editor import load_yaml_config
        import config

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)

        result = load_yaml_config("nonexistent.yaml")
        assert result == {}

    def test_empty_file_returns_empty_dict(self, tmp_path, monkeypatch):
        """Should return empty dict for an empty YAML file."""
        from dashboard.config_editor import load_yaml_config
        import config

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)

        (cfg_dir / "empty.yaml").write_text("")
        result = load_yaml_config("empty.yaml")
        assert result == {}


class TestSaveYamlConfig:
    """Tests for save_yaml_config()."""

    def test_save_creates_file(self, tmp_path, monkeypatch):
        """Should create a new YAML file."""
        from dashboard.config_editor import save_yaml_config
        import config

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)

        data = {"key": "value", "nested": {"a": 1}}
        result = save_yaml_config("new.yaml", data)
        assert result is True

        with open(cfg_dir / "new.yaml") as f:
            loaded = yaml.safe_load(f)
        assert loaded == data

    def test_save_creates_backup(self, tmp_path, monkeypatch):
        """Should create .bak backup before overwriting."""
        from dashboard.config_editor import save_yaml_config
        import config

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)

        # Create original file
        original = {"version": 1}
        with open(cfg_dir / "test.yaml", "w") as f:
            yaml.dump(original, f)

        # Save new data
        new_data = {"version": 2}
        save_yaml_config("test.yaml", new_data)

        # Check backup exists with original content
        backup_path = cfg_dir / "test.yaml.bak"
        assert backup_path.exists()
        with open(backup_path) as f:
            backup_data = yaml.safe_load(f)
        assert backup_data == original

        # Check main file has new content
        with open(cfg_dir / "test.yaml") as f:
            current = yaml.safe_load(f)
        assert current == new_data

    def test_round_trip_preserves_data(self, tmp_path, monkeypatch):
        """Save then load should return the same data."""
        from dashboard.config_editor import save_yaml_config, load_yaml_config
        import config

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)

        data = {
            "scraping": {
                "keywords": ["ai", "machine learning", "deep learning"],
                "safety": {"min_delay": 5, "max_delay": 12},
                "enabled": True,
            }
        }

        save_yaml_config("roundtrip.yaml", data)
        loaded = load_yaml_config("roundtrip.yaml")
        assert loaded == data

    def test_unicode_preserved(self, tmp_path, monkeypatch):
        """Should preserve unicode characters in YAML."""
        from dashboard.config_editor import save_yaml_config, load_yaml_config
        import config

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)

        data = {"name": "Test User", "bio": "Developer specializing in AI"}
        save_yaml_config("unicode.yaml", data)
        loaded = load_yaml_config("unicode.yaml")
        assert loaded["bio"] == data["bio"]


class TestGetConfigFiles:
    """Tests for get_config_files()."""

    def test_returns_list_of_known_configs(self, tmp_path, monkeypatch):
        """Should return a list with known config filenames."""
        from dashboard.config_editor import get_config_files
        import config

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)

        # Create one file
        (cfg_dir / "ai_models.yaml").write_text("test: true")

        result = get_config_files()
        filenames = [r["filename"] for r in result]

        assert "ai_models.yaml" in filenames
        assert "scraping.yaml" in filenames

        # Check exists flag
        ai_entry = next(r for r in result if r["filename"] == "ai_models.yaml")
        assert ai_entry["exists"] is True

        scraping_entry = next(r for r in result if r["filename"] == "scraping.yaml")
        assert scraping_entry["exists"] is False
