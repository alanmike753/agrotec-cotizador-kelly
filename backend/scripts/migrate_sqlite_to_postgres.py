from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert as postgres_insert

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base
from app.migrations import migrate_database
from app.models import DiscountRule, Product, ProductCommercialPreference, Setting


TABLES = [
    (Product.__table__, ["id"]),
    (DiscountRule.__table__, ["scope_type", "scope_key"]),
    (Setting.__table__, ["key"]),
    (ProductCommercialPreference.__table__, ["product_id"]),
]


def normalize_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def backup_sqlite(source: Path) -> Path:
    backup_dir = source.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destination = backup_dir / f"agrotec-pre-postgresql-{stamp}.db"
    with sqlite3.connect(source) as origin, sqlite3.connect(destination) as backup:
        origin.backup(backup)
        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"La copia SQLite no es íntegra: {integrity}")
    return destination


def normalized(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def fingerprint(rows: list[dict[str, Any]], columns: list[str]) -> str:
    payload = [
        {column: normalized(row.get(column)) for column in columns}
        for row in rows
    ]
    payload.sort(key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, default=str))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def rows_for(connection, table) -> list[dict[str, Any]]:
    return [dict(row._mapping) for row in connection.execute(select(table)).all()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra datos comerciales de SQLite a PostgreSQL de forma idempotente.")
    parser.add_argument("--source", default=str(BACKEND_DIR / "agrotec.db"))
    parser.add_argument("--target-url", default=os.getenv("TARGET_DATABASE_URL", ""))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    if not source_path.exists():
        raise SystemExit(f"No existe la base SQLite: {source_path}")
    if not args.target_url:
        raise SystemExit("Indica --target-url o TARGET_DATABASE_URL.")
    target_url = normalize_url(args.target_url)
    if not target_url.startswith("postgresql+psycopg://"):
        raise SystemExit("El destino debe ser PostgreSQL; se rechazó sobrescribir otra base SQLite.")

    backup = backup_sqlite(source_path) if not args.verify_only else None
    source_engine = create_engine(f"sqlite:///{source_path}")
    target_engine = create_engine(target_url, pool_pre_ping=True)
    migrate_database(target_engine)

    source_metadata = MetaData()
    source_metadata.reflect(source_engine)
    reports: list[dict[str, Any]] = []

    with source_engine.connect() as source, target_engine.begin() as target:
        for destination_table, conflict_columns in TABLES:
            if destination_table.name not in source_metadata.tables:
                continue
            source_table = source_metadata.tables[destination_table.name]
            source_rows = rows_for(source, source_table)
            destination_columns = {column.name for column in destination_table.columns}
            transferable = [column.name for column in source_table.columns if column.name in destination_columns]
            records = [{key: row[key] for key in transferable} for row in source_rows]
            if records and not args.verify_only:
                statement = postgres_insert(destination_table).values(records)
                updates = {
                    column: getattr(statement.excluded, column)
                    for column in transferable if column not in conflict_columns and column != "id"
                }
                target.execute(statement.on_conflict_do_update(index_elements=conflict_columns, set_=updates))

            target_rows = rows_for(target, destination_table)
            comparison_columns = [column for column in transferable if not column.endswith("_at")]
            source_hash = fingerprint(source_rows, comparison_columns)
            target_hash = fingerprint(target_rows, comparison_columns)
            reports.append({
                "table": destination_table.name,
                "source_count": len(source_rows),
                "target_count": len(target_rows),
                "source_sha256": source_hash,
                "target_sha256": target_hash,
                "matches": len(source_rows) == len(target_rows) and source_hash == target_hash,
            })

        if not args.verify_only:
            target.execute(text("""
                SELECT setval(
                    pg_get_serial_sequence('discount_rules', 'id'),
                    GREATEST(COALESCE((SELECT MAX(id) FROM discount_rules), 1), 1),
                    true
                )
            """))

    source_engine.dispose()
    target_engine.dispose()
    result = {"backup": str(backup) if backup else None, "tables": reports}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(item["matches"] for item in reports):
        raise SystemExit("La validación detectó diferencias; no publiques hasta revisarlas.")


if __name__ == "__main__":
    main()
