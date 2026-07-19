"""
Multi-tenant migration script
==============================
Run this ONCE on any existing single-tenant database before starting the
updated app for the first time.

Usage:
    python scripts/migrate_to_multitenant.py

What it does:
  1. Creates the `restaurants` table if missing.
  2. Inserts a default "Demo Restaurant" (slug: demo).
  3. Adds `restaurant_id` column to every table that needs it.
  4. Back-fills all existing rows with the demo restaurant's id.
  5. Creates the superadmin user (restaurant_id = NULL).

After running, start the app normally with:
    python run.py
"""

import sqlite3
import os
import sys

# Locate the database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "data", "restaurant.db")

if not os.path.exists(DB_PATH):
    print(f"Database not found at {DB_PATH}")
    print("Nothing to migrate — the app will create a fresh DB on first run.")
    sys.exit(0)

print(f"Migrating: {DB_PATH}")
con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# ── 1. Create restaurants table ───────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS restaurants (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    phone      TEXT,
    address    TEXT,
    vat_number TEXT,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# ── 2. Insert default restaurant ──────────────────────────────────────────────
cur.execute("SELECT id FROM restaurants WHERE slug = 'demo'")
row = cur.fetchone()
if row:
    demo_id = row[0]
    print(f"  Demo restaurant already exists (id={demo_id})")
else:
    cur.execute(
        "INSERT INTO restaurants (name, slug, is_active) VALUES (?, ?, 1)",
        ("Demo Restaurant", "demo"),
    )
    demo_id = cur.lastrowid
    print(f"  Created Demo Restaurant (id={demo_id}, slug=demo)")

# ── 3. Add restaurant_id columns ──────────────────────────────────────────────
TABLES_NEEDING_RID = [
    "users",
    "categories",
    "menu_items",
    "restaurant_tables",
    "orders",
    "bills",
    "customers",
    "ingredients",
    "app_settings",
]

def column_exists(table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())

def table_exists(table):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None

for tbl in TABLES_NEEDING_RID:
    if not table_exists(tbl):
        print(f"  Skipping {tbl} (table does not exist yet)")
        continue
    if column_exists(tbl, "restaurant_id"):
        print(f"  {tbl}.restaurant_id already exists — skipping")
    else:
        cur.execute(f"ALTER TABLE {tbl} ADD COLUMN restaurant_id INTEGER REFERENCES restaurants(id)")
        print(f"  Added {tbl}.restaurant_id")

# ── 4. Back-fill existing rows ────────────────────────────────────────────────
for tbl in TABLES_NEEDING_RID:
    if not table_exists(tbl):
        continue
    cur.execute(f"UPDATE {tbl} SET restaurant_id = ? WHERE restaurant_id IS NULL", (demo_id,))
    affected = cur.rowcount
    if affected:
        print(f"  Back-filled {affected} rows in {tbl}")

# ── 5. Drop old global unique index on users.username (replaced per-restaurant) ─
cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users' AND name='ix_users_username'")
if cur.fetchone():
    cur.execute("DROP INDEX ix_users_username")
    print("  Dropped old unique index on users.username")

# ── 6. Ensure superadmin exists (restaurant_id = NULL) ────────────────────────
cur.execute("SELECT id FROM users WHERE role='superadmin' AND restaurant_id IS NULL")
if cur.fetchone():
    print("  Superadmin already exists — skipping")
else:
    # Use bcrypt hash of "superadmin123"
    try:
        import bcrypt
        pw_hash = bcrypt.hashpw(b"superadmin123", bcrypt.gensalt()).decode()
    except ImportError:
        pw_hash = "$2b$12$placeholder_change_this_password_immediately"
        print("  WARNING: bcrypt not available — set superadmin password manually after migration")

    cur.execute("""
        INSERT INTO users (restaurant_id, username, password_hash, full_name, role, is_active)
        VALUES (NULL, 'superadmin', ?, 'Platform Administrator', 'superadmin', 1)
    """, (pw_hash,))
    print("  Created superadmin user (username: superadmin / password: superadmin123)")

con.commit()
con.close()
print("\nMigration complete. Start the app with:  python run.py")
