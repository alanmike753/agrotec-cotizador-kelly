import sqlite3
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.migrations import migrate_database


def test_old_sqlite_schema_migrates_without_data_loss():
    path = Path(__file__).parent / f"test-migration-{uuid4().hex}.db"
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE products (
            id VARCHAR(64) PRIMARY KEY, name VARCHAR(255), supplier_code VARCHAR(120),
            category VARCHAR(80), family VARCHAR(255), list_price VARCHAR(40),
            source_sheet VARCHAR(80), source_row INTEGER, source_model_column VARCHAR(8),
            source_price_column VARCHAR(8), source_rule_code VARCHAR(120),
            imported_at DATETIME, updated_at DATETIME
        )
    """)
    connection.execute("""
        INSERT INTO products VALUES (
            'implementos-test', 'MODELO ORIGINAL', NULL, 'Implementos', NULL, '12345',
            'Implementos', 9, 'A', 'C', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
    """)
    connection.commit()
    connection.close()

    target_engine = create_engine(f"sqlite:///{path}")
    result = migrate_database(target_engine)
    columns = {item["name"] for item in inspect(target_engine).get_columns("products")}
    tables = set(inspect(target_engine).get_table_names())
    with target_engine.connect() as migrated:
        product = migrated.execute(text("SELECT name, list_price FROM products WHERE id='implementos-test'")).one()
        versions = migrated.execute(text("SELECT version FROM schema_migrations ORDER BY version")).scalars().all()

    assert result["applied"] == [1, 2, 3, 4]
    assert {"default_markup_pct", "family_status", "family_source_label"}.issubset(columns)
    assert "product_commercial_preferences" in tables
    assert product == ("MODELO ORIGINAL", "12345")
    assert versions == [1, 2, 3, 4]
    target_engine.dispose()
    path.unlink()


def test_discount_policy_migration_updates_existing_rules_once():
    path = Path(__file__).parent / f"test-policy-migration-{uuid4().hex}.db"
    target_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(target_engine)
    with target_engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL, applied_at DATETIME NOT NULL
            )
        """))
        connection.execute(text("""
            INSERT INTO schema_migrations VALUES
                (1, 'legacy_product_markup', CURRENT_TIMESTAMP),
                (2, 'commercial_families_and_preferences', CURRENT_TIMESTAMP)
        """))
        connection.execute(text("""
            INSERT INTO discount_rules
                (scope_type, scope_key, name, discounts_json, explicit_zero, source, updated_at)
            VALUES
                ('family', 'Rastras', 'Anterior', '["57", "3", "10"]', 0, 'Prueba', CURRENT_TIMESTAMP)
        """))

    first = migrate_database(target_engine)
    second = migrate_database(target_engine)
    with target_engine.connect() as migrated:
        discounts = migrated.execute(text("SELECT discounts_json FROM discount_rules")).scalar_one()
        versions = migrated.execute(text("SELECT version FROM schema_migrations ORDER BY version")).scalars().all()

    assert first["applied"] == [3, 4]
    assert second["applied"] == []
    assert discounts == '["57.5", "3", "10"]'
    assert versions == [1, 2, 3, 4]
    target_engine.dispose()
    path.unlink()
