#!/usr/bin/env python3
"""Migrate data from local SQLite to Neon PostgreSQL.

Usage:
    DATABASE_URL="postgresql://user:pass@host/db?sslmode=require" python scripts/migrate_to_postgres.py

Reads all data from the local SQLite database and bulk-inserts it into PostgreSQL.
Requires DATABASE_URL environment variable to be set.
"""

import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def migrate():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Usage: DATABASE_URL='postgresql://...' python scripts/migrate_to_postgres.py")
        sys.exit(1)

    import config

    # Connect to local SQLite
    sqlite_path = config.DB_PATH
    if not sqlite_path.exists():
        print(f"ERROR: SQLite database not found at {sqlite_path}")
        sys.exit(1)

    print(f"Source: SQLite at {sqlite_path}")
    print(f"Target: PostgreSQL at {database_url[:50]}...")
    print()

    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    # Initialize PostgreSQL schema via our adapter
    from database.db import init_db
    from database.adapter import get_connection

    print("Initializing PostgreSQL schema...")
    init_db()

    # Use our adapter for the PG connection (handles pooler/SSL properly)
    pg_conn = get_connection()

    # ── Migrate jobs ──────────────────────────────────────────────────────────
    print("Migrating jobs...")
    jobs = sqlite_conn.execute("SELECT * FROM jobs").fetchall()
    if jobs:
        cols = jobs[0].keys()
        col_names = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))

        # Use ON CONFLICT to handle duplicates
        update_cols = [c for c in cols if c != "uid"]
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

        insert_sql = (
            f"INSERT INTO jobs ({col_names}) VALUES ({placeholders}) "
            f"ON CONFLICT (uid) DO UPDATE SET {update_set}"
        )

        batch = []
        for row in jobs:
            batch.append(tuple(row[c] for c in cols))

        # Execute in batches of 100
        batch_size = 100
        for i in range(0, len(batch), batch_size):
            chunk = batch[i : i + batch_size]
            for record in chunk:
                pg_conn.execute(insert_sql, record)
            pg_conn.commit()
            done = min(i + batch_size, len(batch))
            print(f"  Progress: {done}/{len(batch)} jobs...")

        print(f"  Migrated {len(jobs)} jobs")
    else:
        print("  No jobs to migrate")

    # ── Migrate favorites ─────────────────────────────────────────────────────
    print("Migrating favorites...")
    try:
        favs = sqlite_conn.execute("SELECT * FROM favorites").fetchall()
        if favs:
            cols = favs[0].keys()
            col_names = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = (
                f"INSERT INTO favorites ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT (job_uid) DO UPDATE SET "
                f"added_at = EXCLUDED.added_at, notes = EXCLUDED.notes"
            )
            for row in favs:
                pg_conn.execute(insert_sql, tuple(row[c] for c in cols))
            pg_conn.commit()
            print(f"  Migrated {len(favs)} favorites")
        else:
            print("  No favorites to migrate")
    except sqlite3.OperationalError:
        print("  No favorites table found, skipping")

    # ── Migrate proposals ─────────────────────────────────────────────────────
    print("Migrating proposals...")
    try:
        proposals = sqlite_conn.execute("SELECT * FROM proposals").fetchall()
        if proposals:
            # Get column names excluding 'id' (auto-generated in PG)
            all_cols = proposals[0].keys()
            cols = [c for c in all_cols if c != "id"]
            col_names = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))
            insert_sql = (
                f"INSERT INTO proposals ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT DO NOTHING"
            )

            for row in proposals:
                pg_conn.execute(insert_sql, tuple(row[c] for c in cols))
            pg_conn.commit()
            print(f"  Migrated {len(proposals)} proposals")
        else:
            print("  No proposals to migrate")
    except sqlite3.OperationalError:
        print("  No proposals table found, skipping")

    # ── Verify ────────────────────────────────────────────────────────────────
    print()
    print("Verification:")
    cur = pg_conn.execute("SELECT COUNT(*) as cnt FROM jobs")
    print(f"  Jobs in PostgreSQL: {cur.fetchone()['cnt']}")

    cur = pg_conn.execute("SELECT COUNT(*) as cnt FROM favorites")
    print(f"  Favorites in PostgreSQL: {cur.fetchone()['cnt']}")

    cur = pg_conn.execute("SELECT COUNT(*) as cnt FROM proposals")
    print(f"  Proposals in PostgreSQL: {cur.fetchone()['cnt']}")

    # Cleanup
    pg_conn.close()
    sqlite_conn.close()

    print()
    print("Migration complete!")


if __name__ == "__main__":
    migrate()
