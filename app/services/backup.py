"""
Automatic daily database backup.

Runs in a background daemon thread.  On startup it checks whether today's
backup already exists; if not it creates one immediately, then sleeps until
the next midnight and repeats.  Old backups beyond BACKUP_KEEP_DAYS are
pruned automatically.
"""
import logging
import shutil
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.config import DATA_DIR, BACKUP_KEEP_DAYS

_log = logging.getLogger(__name__)

_DB_FILE     = Path(DATA_DIR) / "restaurant.db"
_BACKUP_DIR  = Path(DATA_DIR) / "backups"


def _do_backup() -> Path | None:
    """Copy restaurant.db → backups/restaurant_YYYYMMDD_HHMMSS.db.
    Returns the backup path, or None if the source doesn't exist."""
    if not _DB_FILE.exists():
        _log.warning("Backup skipped — database file not found: %s", _DB_FILE)
        return None

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = _BACKUP_DIR / f"restaurant_{ts}.db"
    shutil.copy2(_DB_FILE, dest)
    _log.info("Backup created: %s", dest.name)
    _prune_old_backups()
    return dest


def _prune_old_backups():
    """Delete backup files older than BACKUP_KEEP_DAYS days."""
    cutoff = time.time() - BACKUP_KEEP_DAYS * 86400
    for f in _BACKUP_DIR.glob("restaurant_*.db"):
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


def _backup_loop():
    """Background thread: back up once now (if needed), then nightly."""
    # Check whether today already has a backup
    today_tag = datetime.now().strftime("%Y%m%d")
    existing  = list(_BACKUP_DIR.glob(f"restaurant_{today_tag}_*.db"))
    if not existing:
        _do_backup()

    while True:
        sleep_secs = _seconds_until_midnight()
        _log.debug("Next backup in %.0f s", sleep_secs)
        time.sleep(sleep_secs)
        _do_backup()


def start_backup_scheduler():
    """Start the nightly backup thread.  Call once at application startup."""
    t = threading.Thread(target=_backup_loop, name="backup-scheduler", daemon=True)
    t.start()
    _log.info("Backup scheduler started (keep_days=%d)", BACKUP_KEEP_DAYS)


def backup_now() -> dict:
    """Trigger an immediate backup and return info about the file created."""
    dest = _do_backup()
    if dest:
        return {"ok": True, "file": dest.name, "size_kb": round(dest.stat().st_size / 1024, 1)}
    return {"ok": False, "detail": "Database file not found"}
