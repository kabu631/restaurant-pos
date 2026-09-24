"""
Copy all restaurant data from one database to another — e.g. PostgreSQL → XAMPP MySQL.

    python scripts/copy_database.py --from postgresql://postgres:pw@localhost:5432/restaurant_pos \
                                    --to   "mysql+pymysql://root:@localhost:3306/restaurant_pos?charset=utf8mb4"

The target gets the current schema first; then every table is copied with its IDs,
so bill numbers, orders and logins stay exactly the same.  The source is only read.
The target must be empty (use --replace to wipe it first).
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="source", required=True, help="source database URL")
    parser.add_argument("--to", dest="target", required=True, help="target database URL")
    parser.add_argument("--replace", action="store_true", help="delete rows already in the target first")
    args = parser.parse_args()

    # The app builds its engine from DATABASE_URL at import time — point it at the target
    os.environ["DATABASE_URL"] = args.target
    from sqlalchemy import MetaData, create_engine, select, text
    import app.models  # noqa: F401 — registers every table
    from app.database import Base, create_tables, engine as target

    create_tables()                                   # current schema on the target
    source = create_engine(args.source)
    src_meta = MetaData()
    src_meta.reflect(bind=source)
    tables = Base.metadata.sorted_tables              # parents before children

    with target.begin() as tconn:
        non_empty = [t.name for t in tables if tconn.execute(select(t).limit(1)).first()]
        if non_empty and not args.replace:
            sys.exit(f"Target already has data in {non_empty}. Re-run with --replace to overwrite it.")
        if target.dialect.name == "mysql":
            tconn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for t in reversed(tables):
            if args.replace:
                tconn.execute(t.delete())

        with source.connect() as sconn:
            for t in tables:
                if t.name not in src_meta.tables:
                    print(f"  {t.name:22s} (new table — nothing to copy)")
                    continue
                src = src_meta.tables[t.name]
                cols = [c.name for c in t.columns if c.name in src.columns]
                rows = [dict(r._mapping) for r in sconn.execute(select(*[src.c[c] for c in cols]))]
                if rows:
                    tconn.execute(t.insert(), rows)
                print(f"  {t.name:22s} {len(rows)} row(s)")

        if target.dialect.name == "mysql":
            tconn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        elif target.dialect.name == "postgresql":
            # Move each id sequence past the copied rows
            for t in tables:
                if "id" in t.columns:
                    tconn.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{t.name}\"), 0) + 1, false)"))
    print("Done.")


if __name__ == "__main__":
    main()
