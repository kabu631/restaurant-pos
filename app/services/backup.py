"""
Automatic daily database backup.

Runs in a background daemon thread.  On startup it checks whether today's
backup already exists; if not it creates one immediately, then sleeps until
the next midnight and repeats.  Old backups beyond BACKUP_KEEP_DAYS are
pruned automatically.

  - PostgreSQL → pg_dump to data/backups/restaurant_YYYYMMDD_HHMMSS.sql
    (restore with:  psql -d restaurant_pos -f <file>)
  - MySQL / MariaDB (XAMPP) → mysqldump, same file name
    (restore with:  mysql -u root restaurant_pos < <file>, or phpMyAdmin → Import)
  - SQLite     → consistent copy via the SQLite online-backup API (.db)
"""
import glob
import logging
import os
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.engine import make_url

from app.config import BACKUP_KEEP_DAYS, DATA_DIR, DATABASE_URL, PG_DUMP_PATH

_log = logging.getLogger(__name__)

_BACKUP_DIR = Path(DATA_DIR) / "backups"
_PATTERNS = ("restaurant_*.sql", "restaurant_*.db")
_lock = threading.Lock()


class BackupError(RuntimeError):
    pass


def _find_pg_dump() -> Optional[str]:
    if PG_DUMP_PATH and Path(PG_DUMP_PATH).exists():
        return PG_DUMP_PATH
    found = shutil.which("pg_dump")
    if found:
        return found
    # Default Windows installs: C:\Program Files\PostgreSQL\<version>\bin\pg_dump.exe
    candidates = glob.glob(r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe")
    candidates.sort(key=lambda p: [int(x) if x.isdigit() else x
                                   for x in Path(p).parent.parent.name.split(".")])
    return candidates[-1] if candidates else None


def _backup_postgres(dest: Path) -> None:
    exe = _find_pg_dump()
    if not exe:
        raise BackupError("pg_dump was not found. Install the PostgreSQL command-line tools "
                          "or set PG_DUMP_PATH in .env")
    url = make_url(DATABASE_URL)
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    cmd = [exe, "--no-owner", "--no-privileges", "-f", str(dest),
           "-h", url.host or "localhost", "-p", str(url.port or 5432),
           "-U", url.username or "postgres", url.database]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(cmd, env=env, capture_output=True, text=True,
                            timeout=900, creationflags=flags)
    if result.returncode != 0:
        dest.unlink(missing_ok=True)
        raise BackupError(f"pg_dump failed: {(result.stderr or result.stdout).strip()[:300]}")


def _find_mysqldump() -> Optional[str]:
    found = shutil.which("mysqldump")
    if found:
        return found
    for candidate in (r"C:\xampp\mysql\bin\mysqldump.exe", r"D:\xampp\mysql\bin\mysqldump.exe"):
        if Path(candidate).exists():
            return candidate
    return None


def _backup_mysql(dest: Path) -> None:
    exe = _find_mysqldump()
    if not exe:
        raise BackupError("mysqldump was not found (it comes with XAMPP in C:\\xampp\\mysql\\bin)")
    url = make_url(DATABASE_URL)
    env = dict(os.environ)
    if url.password:
        env["MYSQL_PWD"] = url.password
    cmd = [exe, "--single-transaction", "--default-character-set=utf8mb4",
           "-h", url.host or "localhost", "-P", str(url.port or 3306),
           "-u", url.username or "root", f"--result-file={dest}", url.database]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(cmd, env=env, capture_output=True, text=True,
                            timeout=900, creationflags=flags)
    if result.returncode != 0:
        dest.unlink(missing_ok=True)
        raise BackupError(f"mysqldump failed: {(result.stderr or result.stdout).strip()[:300]}")


def _backup_sqlite(dest: Path) -> None:
    source = make_url(DATABASE_URL).database
    if not source or not Path(source).exists():
        raise BackupError(f"Database file not found: {source}")
    with sqlite3.connect(source) as src, sqlite3.connect(dest) as out:
        src.backup(out)


def _do_backup() -> Path:
    """Write one backup file and return its path; raises BackupError on failure."""
    backend = make_url(DATABASE_URL).get_backend_name()
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with _lock:
        if backend == "postgresql":
            dest = _BACKUP_DIR / f"restaurant_{ts}.sql"
            _backup_postgres(dest)
        elif backend in ("mysql", "mariadb"):
            dest = _BACKUP_DIR / f"restaurant_{ts}.sql"
            _backup_mysql(dest)
        elif backend == "sqlite":
            dest = _BACKUP_DIR / f"restaurant_{ts}.db"
            _backup_sqlite(dest)
        else:
            raise BackupError(f"Automatic backup is not supported for {backend}")
    _log.info("Backup created: %s", dest.name)
    _prune_old_backups()
    return dest


def _backup_files() -> list[Path]:
    files = [f for pattern in _PATTERNS for f in _BACKUP_DIR.glob(pattern)]
    return sorted(files, key=lambda f: f.name, reverse=True)


def _prune_old_backups():
    """Delete backup files older than BACKUP_KEEP_DAYS days."""
    cutoff = time.time() - BACKUP_KEEP_DAYS * 86400
    for f in _backup_files():
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            _log.info("Pruned old backup: %s", f.name)


def _seconds_until_midnight() -> float:
    """Seconds from now until the next local midnight + 5 minutes."""
    now      = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=5, second=0, microsecond=0
    )
    return (tomorrow - now).total_seconds()


def _safe_backup():
    try:
        _do_backup()
    except Exception:
        _log.exception("Scheduled backup failed")


def _backup_loop():
    """Background thread: back up once now (if needed), then nightly."""
    today_tag = datetime.now().strftime("%Y%m%d")
    if not any(f.name.startswith(f"restaurant_{today_tag}_") for f in _backup_files()):
        _safe_backup()

    while True:
        sleep_secs = _seconds_until_midnight()
        _log.debug("Next backup in %.0f s", sleep_secs)
        time.sleep(sleep_secs)
        _safe_backup()


def start_backup_scheduler():
    """Start the nightly backup thread.  Call once at application startup."""
    t = threading.Thread(target=_backup_loop, name="backup-scheduler", daemon=True)
    t.start()
    _log.info("Backup scheduler started (keep_days=%d)", BACKUP_KEEP_DAYS)


def backup_now() -> dict:
    """Trigger an immediate backup and return info about the file created."""
    try:
        dest = _do_backup()
    except BackupError as exc:
        return {"ok": False, "detail": str(exc)}
    except Exception as exc:
        _log.exception("Backup failed")
        return {"ok": False, "detail": f"Backup failed: {exc}"}
    return {"ok": True, "file": dest.name, "size_kb": round(dest.stat().st_size / 1024, 1)}


def list_backups() -> list:
    if not _BACKUP_DIR.exists():
        return []
    return [
        {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)}
        for f in _backup_files()[:30]
    ]
