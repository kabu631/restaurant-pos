import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (the directory that contains this package)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=False)   # won't override already-set env vars

# ── Application ───────────────────────────────────────────────────────────────
APP_NAME    = "Restaurant Management & Billing System"
APP_VERSION = "1.0.0"

# ── Database ──────────────────────────────────────────────────────────────────
BASE_DIR     = str(_ROOT)
DATA_DIR     = str(_ROOT / "data")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/restaurant_pos",
)

# ── Tax settings ──────────────────────────────────────────────────────────────
VAT_RATE              = 13.0   # IRD-mandated 13% VAT
SERVICE_CHARGE_RATE   = 10.0   # Optional 10% service charge
SERVICE_CHARGE_ENABLED = True

# ── Nepal locale ──────────────────────────────────────────────────────────────
CURRENCY = "NPR"
TIMEZONE = "Asia/Kathmandu"   # UTC+5:45

# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY                  = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480   # 8 hours

# ── Server ────────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# ── FonePay merchant credentials ──────────────────────────────────────────────
FONEPAY_MERCHANT_CODE     = os.getenv("FONEPAY_MERCHANT_CODE",     "DEMO_PID")
FONEPAY_MERCHANT_PASSWORD = os.getenv("FONEPAY_MERCHANT_PASSWORD", "DEMO_MD")
FONEPAY_SECRET_KEY        = os.getenv("FONEPAY_SECRET_KEY",        "DEMO_SECRET")
FONEPAY_BASE_URL          = os.getenv("FONEPAY_BASE_URL",          "https://dev-clientapi.fonepay.com/api/")
FONEPAY_CALLBACK_BASE     = os.getenv("FONEPAY_CALLBACK_BASE",     f"http://{HOST}:{PORT}")

# ── Thermal printer ───────────────────────────────────────────────────────────
THERMAL_PRINTER_PATH = os.getenv("THERMAL_PRINTER_PATH", "")   # e.g. "COM3" or "/dev/usb/lp0"

# ── Cloud sync ────────────────────────────────────────────────────────────────
CLOUD_SYNC_URL = os.getenv("CLOUD_SYNC_URL", "")

# ── Backup ────────────────────────────────────────────────────────────────────
BACKUP_KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "30"))
