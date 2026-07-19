import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

from app.config import DATABASE_URL

_log = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

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
    """Add columns introduced after the initial schema — safe to run repeatedly."""
    migrations = [
        # table,          column,         DDL type
        ("users",       "last_login",    "TIMESTAMP"),
        ("users",       "created_at",    "TIMESTAMP DEFAULT NOW()"),
        ("users",       "updated_at",    "TIMESTAMP DEFAULT NOW()"),
        ("bills",       "fiscal_year",   "VARCHAR"),
        ("bills",       "fonepay_prn",   "VARCHAR"),
        ("audit_trail", "restaurant_id", "INTEGER"),
        ("audit_trail", "reason",        "VARCHAR"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :t AND column_name = :c"
                    ),
                    {"t": table, "c": column},
                )
                if result.fetchone() is None:
                    conn.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}')
                    )
                    conn.commit()
                    _log.info("Migrated: ALTER TABLE %s ADD COLUMN %s", table, column)
            except Exception:
                _log.exception("Migration skipped for %s.%s", table, column)
