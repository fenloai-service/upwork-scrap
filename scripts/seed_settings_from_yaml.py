#!/usr/bin/env python3
"""Seed the settings table from existing YAML config files.

Reads all 7 config YAML files and upserts them into the database settings table.
Safe to run multiple times (upsert semantics). Works with both SQLite and PostgreSQL.

Usage:
    python -m scripts.seed_settings_from_yaml
    # or
    python scripts/seed_settings_from_yaml.py
"""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

import config
from database.db import init_db, save_setting

# Mapping of YAML filenames to settings keys
CONFIG_FILES = {
    "scraping.yaml": "scraping",
    "ai_models.yaml": "ai_models",
    "user_profile.yaml": "user_profile",
    "projects.yaml": "projects",
    "proposal_guidelines.yaml": "proposal_guidelines",
    "job_preferences.yaml": "job_preferences",
    "email_config.yaml": "email_config",
}


def seed_settings():
    """Read all YAML config files and upsert into the settings table."""
    init_db()

    seeded = 0
    skipped = 0
    failed = 0

    for filename, key in CONFIG_FILES.items():
        filepath = config.CONFIG_DIR / filename
        if not filepath.exists():
            print(f"  SKIP  {filename} (file not found)")
            skipped += 1
            continue

        try:
            with open(filepath) as f:
                data = yaml.safe_load(f)
            if data is None:
                data = {}

            if save_setting(key, data):
                print(f"  OK    {filename} -> settings['{key}']")
                seeded += 1
            else:
                print(f"  FAIL  {filename} (save_setting returned False)")
                failed += 1
        except Exception as e:
            print(f"  FAIL  {filename}: {e}")
            failed += 1

    print(f"\nDone: {seeded} seeded, {skipped} skipped, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    print("Seeding settings table from YAML config files...\n")
    success = seed_settings()
    sys.exit(0 if success else 1)
