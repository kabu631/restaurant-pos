import logging
import re
from contextlib import contextmanager

from sqlalchemy import Float, String, Text, create_engine, inspect, text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

from app.config import DATABASE_URL, TIMEZONE

_log = logging.getLogger(__name__)


# ── MySQL / MariaDB (XAMPP) column types ───────────────────────────────────────
# The models use plain String/Float/Text; these only change the DDL MySQL receives.

@compiles(String, "mysql")
def _mysql_string(type_, compiler, **kw):
    # MySQL requires a length; long free text uses Text columns instead
    return f"VARCHAR({type_.length or 255})"


@compiles(Float, "mysql")
def _mysql_float(type_, compiler, **kw):
    # MySQL FLOAT is single precision and rounds rupee amounts — use DOUBLE
    return "DOUBLE"


@compiles(Text, "mysql")
def _mysql_text(type_, compiler, **kw):
    # TEXT stops at 64 KB; uploaded payment QR images are bigger
    return "MEDIUMTEXT"


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    kwargs = {"pool_pre_ping": True}
    if url.startswith("postgresql"):
        # Pin the session timezone: all timestamps are stored as naive Nepal time,
        # regardless of how the PostgreSQL server itself is configured.
        kwargs["connect_args"] = {"options": f"-c timezone={TIMEZONE}"}
    elif url.startswith("mysql"):
        # Nepal time for NOW() defaults, full Unicode for Nepali menu names,
        # and recycle connections before MySQL's idle timeout drops them.
        kwargs["pool_recycle"] = 3600
        kwargs["connect_args"] = {"charset": "utf8mb4", "init_command": "SET time_zone = '+05:45'"}
    return kwargs


engine = create_engine(DATABASE_URL, **_engine_kwargs(DATABASE_URL))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_transaction(db: Session):
    """Wraps a block in BEGIN/COMMIT; rolls back and raises 500 on unexpected errors."""
    try:
        yield db
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        _log.exception("Unexpected database error — rolled back")
        raise HTTPException(
            status_code=500,
            detail="An unexpected server error occurred. The operation was rolled back.",
        )


def create_tables():
    Base.metadata.create_all(bind=engine)
    _migrate_columns()


def _migrate_columns():
    """Add columns introduced after the initial schema — safe to run repeatedly.

    New tables are created by create_all(); this only patches existing tables.
    """
    migrations = [
        # table,          column,             DDL type
        ("users",       "last_login",       "TIMESTAMP"),
        ("users",       "created_at",       "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("users",       "updated_at",       "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("bills",       "fiscal_year",      "VARCHAR"),
        ("bills",       "fonepay_prn",      "VARCHAR"),
        ("audit_trail", "restaurant_id",    "INTEGER"),
        ("audit_trail", "reason",           "VARCHAR"),
        ("orders",      "guests",           "INTEGER"),
        ("orders",      "delivery_address", "VARCHAR"),
        ("categories",  "station",          "VARCHAR DEFAULT 'kitchen'"),
        ("users",       "last_seen_at",     "TIMESTAMP"),
        ("users",       "session_version",  "INTEGER NOT NULL DEFAULT 0"),
        ("users",       "shift_start",      "VARCHAR(5)"),
        ("users",       "shift_end",        "VARCHAR(5)"),
    ]
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    quote = engine.dialect.identifier_preparer.quote   # "x" on PostgreSQL, `x` on MySQL
    for table, column, col_type in migrations:
        if table not in existing_tables:
            continue
        if column in {c["name"] for c in inspector.get_columns(table)}:
            continue
        if engine.dialect.name == "mysql":
            col_type = re.sub(r"VARCHAR(?!\()", "VARCHAR(255)", col_type)
        try:
            # One transaction per column so a failure cannot poison the others
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {quote(table)} ADD COLUMN {quote(column)} {col_type}"))
            _log.info("Migrated: ALTER TABLE %s ADD COLUMN %s", table, column)
        except Exception:
            _log.exception("Migration skipped for %s.%s", table, column)
