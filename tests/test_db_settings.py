"""Tests for database settings CRUD (key-value config store).

Run: pytest tests/test_db_settings.py -v
"""

import sqlite3

import pytest

import config
from database.db import (
    init_db,
    get_setting,
    save_setting,
    get_all_settings,
    load_config_from_db,
    VALID_SETTING_KEYS,
)


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Point the database at a temporary SQLite file for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    init_db()


class TestGetSetting:
    """Tests for get_setting()."""

    def test_returns_none_for_missing_key(self):
        assert get_setting("scraping") is None

    def test_returns_saved_value(self):
        save_setting("scraping", {"keywords": ["ai"]})
        result = get_setting("scraping")
        assert result == {"keywords": ["ai"]}

    def test_returns_none_for_unknown_key(self):
        """Keys not in VALID_SETTING_KEYS can't be saved, so get returns None."""
        assert get_setting("nonexistent") is None


class TestSaveSetting:
    """Tests for save_setting()."""

    def test_save_and_retrieve(self):
        data = {"ai_models": {"provider": "xai", "model": "grok-3"}}
        assert save_setting("ai_models", data) is True
        assert get_setting("ai_models") == data

    def test_upsert_overwrites(self):
        save_setting("scraping", {"v": 1})
        save_setting("scraping", {"v": 2})
        assert get_setting("scraping") == {"v": 2}

    def test_rejects_invalid_key(self):
        assert save_setting("invalid_key", {"a": 1}) is False

    def test_saves_complex_nested_data(self):
        data = {
            "preferences": {
                "categories": ["ai_agent", "rag_doc_ai"],
                "budget": {"min_fixed": 500, "min_hourly": 30},
                "nested": {"deep": {"value": True}},
            }
        }
        save_setting("job_preferences", data)
        assert get_setting("job_preferences") == data

    def test_saves_unicode(self):
        data = {"name": "Test User", "bio": "Specializing in AI & ML"}
        save_setting("user_profile", data)
        assert get_setting("user_profile") == data

    def test_all_valid_keys_accepted(self):
        for key in VALID_SETTING_KEYS:
            assert save_setting(key, {"test": True}) is True


class TestGetAllSettings:
    """Tests for get_all_settings()."""

    def test_empty_db(self):
        assert get_all_settings() == {}

    def test_returns_all_saved(self):
        save_setting("scraping", {"a": 1})
        save_setting("ai_models", {"b": 2})
        result = get_all_settings()
        assert result == {"scraping": {"a": 1}, "ai_models": {"b": 2}}


class TestLoadConfigFromDb:
    """Tests for load_config_from_db()."""

    def test_returns_none_when_empty(self):
        assert load_config_from_db("scraping") is None

    def test_returns_saved_data(self):
        save_setting("ai_models", {"provider": "xai"})
        assert load_config_from_db("ai_models") == {"provider": "xai"}

    def test_strips_yaml_suffix(self):
        save_setting("scraping", {"keywords": ["ai"]})
        assert load_config_from_db("scraping.yaml") == {"keywords": ["ai"]}

    def test_handles_errors_gracefully(self, monkeypatch):
        """Should return None on any exception."""
        import database.db as db_mod
        monkeypatch.setattr(db_mod, "get_setting", lambda k: (_ for _ in ()).throw(RuntimeError("boom")))
        assert load_config_from_db("scraping") is None
