"""
SQLite → PostgreSQL data migration
====================================
Run this ONCE to copy all existing data from the SQLite file into PostgreSQL.

Prerequisites:
  1. Create the target database in pgAdmin:
       Right-click Databases → Create → Database → name it "restaurant_pos" → Save
  2. Make sure DATABASE_URL in .env points to that PostgreSQL database.
  3. Install dependencies:  pip install -r requirements.txt

Usage (from the project root):
    python scripts/migrate_sqlite_to_postgres.py

The script:
  - Creates all tables in PostgreSQL (via SQLAlchemy models)
  - Copies every row from every table in the SQLite file
  - Casts SQLite integer booleans (0/1) to PostgreSQL booleans
  - Resets PostgreSQL sequences so auto-increment IDs continue from the right value
  - Is safe to re-run: existing rows are skipped (INSERT … ON CONFLICT DO NOTHING)
"""

import os
import sys
import sqlite3

# Add project root to path so app imports work
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SQLITE_PATH = os.path.join(ROOT, "data", "restaurant.db")

# ── Validate SQLite source ────────────────────────────────────────────────────
if not os.path.exists(SQLITE_PATH):
    print(f"SQLite database not found at {SQLITE_PATH}")
    print("Nothing to migrate. The app will create a fresh schema on first run.")
    sys.exit(0)

# ── Load environment & connect to PostgreSQL ──────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from sqlalchemy import create_engine, text, inspect, Boolean
from app.config import DATABASE_URL

if "sqlite" in DATABASE_URL:
    print("ERROR: DATABASE_URL still points to SQLite. Update .env to use PostgreSQL.")
    sys.exit(1)

print(f"Source : {SQLITE_PATH}")
print(f"Target : {DATABASE_URL}\n")

pg_engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ── Create schema in PostgreSQL ───────────────────────────────────────────────
print("Creating tables in PostgreSQL …")
import app.models  # registers all models on Base
from app.database import Base

Base.metadata.create_all(bind=pg_engine)
print("  Tables created.\n")

# ── Build a map of boolean columns per table from the SQLAlchemy models ───────
bool_columns: dict[str, set[str]] = {}
for table_name, table_obj in Base.metadata.tables.items():
    bools = {col.name for col in table_obj.columns if isinstance(col.type, Boolean)}
    if bools:
        bool_columns[table_name] = bools

# ── Copy data table by table ──────────────────────────────────────────────────
sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row

# Migration order matters — respect foreign-key dependencies
TABLE_ORDER = [
    "restaurants",
    "users",
    "categories",
    "menu_items",
    "restaurant_tables",
    "customers",
    "orders",
    "order_items",
    "bills",
    "ingredients",
    "stock_purchases",
    "app_settings",
    "recipe_ingredients",
    "audit_trail",
    "sync_log",
]

inspector = inspect(pg_engine)
pg_tables = set(inspector.get_table_names())

with pg_engine.connect() as pg_conn:
    for table in TABLE_ORDER:
        if table not in pg_tables:
            print(f"  Skipping {table} (not in PostgreSQL schema yet)")
            continue

        cur = sqlite_conn.execute(f"SELECT * FROM {table}")  # noqa: S608
        rows = cur.fetchall()

        if not rows:
            print(f"  {table}: empty — skipped")
            continue

        columns = [desc[0] for desc in cur.description]
        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        table_bools = bool_columns.get(table, set())

        inserted = 0
        skipped  = 0
        for row in rows:
            row_dict = dict(zip(columns, row))

            # Cast SQLite 0/1 integers to Python bool for boolean columns
            for col in table_bools:
                if col in row_dict and row_dict[col] is not None:
                    row_dict[col] = bool(row_dict[col])

            try:
                pg_conn.execute(
                    text(
                        f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
                        f"ON CONFLICT DO NOTHING"
                    ),
                    row_dict,
                )
                inserted += 1
            except Exception as exc:
                pg_conn.rollback()
                skipped += 1
                print(f"    WARNING: skipped a row in {table}: {exc}")

        pg_conn.commit()
        print(f"  {table}: {inserted} rows inserted, {skipped} skipped")

sqlite_conn.close()

# ── Reset PostgreSQL sequences ────────────────────────────────────────────────
print("\nResetting sequences …")
with pg_engine.connect() as pg_conn:
    for table in TABLE_ORDER:
        if table not in pg_tables:
            continue
        try:
            pg_conn.execute(
                text(
                    f"SELECT setval("
                    f"  pg_get_serial_sequence('{table}', 'id'),"
                    f"  COALESCE((SELECT MAX(id) FROM \"{table}\"), 1)"
                    f")"
                )
            )
            pg_conn.commit()
            print(f"  {table}: sequence reset")
        except Exception:
            pass  # table has no serial 'id' column — fine

print("\nMigration complete.")
print("Start the app with:  python run.py")
