from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import Engine, inspect, text

from .database import BACKEND_DIR, DATABASE_URL, Base, engine
from . import models as _models  # noqa: F401  Ensures every mapped table is registered for CLI/pre-deploy runs.


Migration = tuple[int, str, Callable[[Engine], None]]


def _columns(target_engine: Engine, table: str) -> set[str]:
    inspector = inspect(target_engine)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _migration_001_legacy_markup(target_engine: Engine) -> None:
    columns = _columns(target_engine, "products")
    if columns and "default_markup_pct" not in columns:
        with target_engine.begin() as connection:
            connection.execute(text("ALTER TABLE products ADD COLUMN default_markup_pct VARCHAR(40)"))


def _migration_002_families_and_preferences(target_engine: Engine) -> None:
    columns = _columns(target_engine, "products")
    timestamp_type = "TIMESTAMP WITH TIME ZONE" if target_engine.dialect.name == "postgresql" else "DATETIME"
    with target_engine.begin() as connection:
        if columns and "family_status" not in columns:
            connection.execute(text(
                "ALTER TABLE products ADD COLUMN family_status VARCHAR(40) NOT NULL DEFAULT 'needs_confirmation'"
            ))
        if columns and "family_source_label" not in columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN family_source_label VARCHAR(255)"))
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS product_commercial_preferences (
                product_id VARCHAR(64) PRIMARY KEY NOT NULL,
                profit_mode VARCHAR(20) NOT NULL DEFAULT 'markup',
                profit_value VARCHAR(40) NOT NULL DEFAULT '25',
                rounding_increment VARCHAR(10) NOT NULL DEFAULT '1',
                updated_at {timestamp_type} NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """))
        # Preserve any per-product markups saved by the previous schema.
        if "default_markup_pct" in columns:
            connection.execute(text("""
                INSERT INTO product_commercial_preferences
                    (product_id, profit_mode, profit_value, rounding_increment, updated_at)
                SELECT id, 'markup', default_markup_pct, '1', CURRENT_TIMESTAMP
                FROM products
                WHERE default_markup_pct IS NOT NULL
                ON CONFLICT(product_id) DO NOTHING
            """))


def _migration_003_kelly_discount_policy(target_engine: Engine) -> None:
    if "discount_rules" not in inspect(target_engine).get_table_names():
        return
    with target_engine.begin() as connection:
        rules = connection.execute(text("SELECT id, discounts_json FROM discount_rules")).all()
        for rule_id, raw_discounts in rules:
            discounts = json.loads(raw_discounts)
            if len(discounts) == 3 and str(discounts[0]) == "57" and str(discounts[1]) == "3":
                discounts[0] = "57.5"
                connection.execute(
                    text("UPDATE discount_rules SET discounts_json=:discounts WHERE id=:rule_id"),
                    {"discounts": json.dumps(discounts), "rule_id": rule_id},
                )


def _migration_004_users_and_sessions(target_engine: Engine) -> None:
    # Base.metadata.create_all creates the portable table definitions first. These
    # indexes make the migration explicit and remain idempotent on SQLite/Postgres.
    with target_engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_sessions_token_hash ON user_sessions (token_hash)"
        ))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_user_sessions_expires_at ON user_sessions (expires_at)"))


MIGRATIONS: list[Migration] = [
    (1, "legacy_product_markup", _migration_001_legacy_markup),
    (2, "commercial_families_and_preferences", _migration_002_families_and_preferences),
    (3, "kelly_fixed_discount_policy", _migration_003_kelly_discount_policy),
    (4, "users_and_secure_sessions", _migration_004_users_and_sessions),
]


def _sqlite_path(target_engine: Engine) -> Path | None:
    database = target_engine.url.database
    if target_engine.url.get_backend_name() != "sqlite" or not database or database == ":memory:":
        return None
    return Path(database).resolve()


def backup_sqlite_database(target_engine: Engine, next_version: int) -> Path | None:
    if os.getenv("AGROTEC_SKIP_MIGRATION_BACKUP") == "1":
        return None
    source = _sqlite_path(target_engine)
    if source is None or not source.exists() or source.stat().st_size == 0:
        return None
    backup_dir = source.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destination = backup_dir / f"agrotec-pre-migration-v{next_version}-{stamp}.db"
    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
        integrity = destination_connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"La copia de seguridad SQLite no es íntegra: {integrity}")
    finally:
        destination_connection.close()
        source_connection.close()
    return destination


def apply_versioned_migrations(target_engine: Engine = engine) -> dict:
    timestamp_type = "TIMESTAMP WITH TIME ZONE" if target_engine.dialect.name == "postgresql" else "DATETIME"
    with target_engine.begin() as connection:
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at {timestamp_type} NOT NULL
            )
        """))
        applied = {row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))}

    pending = [migration for migration in MIGRATIONS if migration[0] not in applied]
    backup = backup_sqlite_database(target_engine, pending[0][0]) if pending else None
    applied_now: list[int] = []
    for version, name, migration in pending:
        migration(target_engine)
        with target_engine.begin() as connection:
            connection.execute(
                text("INSERT INTO schema_migrations(version, name, applied_at) VALUES (:version, :name, :applied_at)"),
                {"version": version, "name": name, "applied_at": datetime.now(timezone.utc)},
            )
        applied_now.append(version)
    return {"applied": applied_now, "backup": str(backup) if backup else None}


def migrate_database(target_engine: Engine = engine) -> dict:
    Base.metadata.create_all(bind=target_engine)
    return apply_versioned_migrations(target_engine)


if __name__ == "__main__":
    print(migrate_database())

