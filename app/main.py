import os
import logging
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import APP_NAME, APP_VERSION, DATA_DIR
from app.database import create_tables, SessionLocal, get_db
import app.models  # noqa: F401 — registers all models with SQLAlchemy metadata
from app.models.restaurant import Restaurant
from app.models.user import User
from app.models.bill import Bill
from app.models.order import Order, OrderItem
from app.models.inventory import AppSettings
from app.utils.security import hash_password
from app.routes import (auth, menu, tables, orders, kitchen,
                        billing, inventory, restaurants, users, reports)
from app.routes import settings as settings_router
from app.routes.auth import get_current_user, require_admin
from app.services import backup as backup_svc
from app.services import printer as printer_svc

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s – %(message)s")
_log = logging.getLogger(__name__)

app = FastAPI(title=APP_NAME, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(restaurants.router)
app.include_router(menu.router)
app.include_router(tables.router)
app.include_router(orders.router)
app.include_router(kitchen.router)
app.include_router(billing.router)
app.include_router(inventory.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(settings_router.router)


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    create_tables()
    _seed()
    backup_svc.start_backup_scheduler()


def _seed():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.role == "superadmin").first():
            superadmin = User(
                restaurant_id=None,
                username="superadmin",
                password_hash=hash_password("superadmin123"),
                full_name="Platform Administrator",
                role="superadmin",
                is_active=True,
            )
            db.add(superadmin)
            db.commit()
            _log.info("Superadmin created → username: superadmin / password: superadmin123")

        if not db.query(Restaurant).filter(Restaurant.slug == "demo").first():
            demo = Restaurant(name="Demo Restaurant", slug="demo", is_active=True)
            db.add(demo)
            db.flush()
            admin = User(
                restaurant_id=demo.id,
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="Administrator",
                role="admin",
                is_active=True,
                pin="0000",
            )
            db.add(admin)
            db.commit()
            _log.info("Demo restaurant created → code: demo / username: admin / password: admin123")
    finally:
        db.close()


# ── Backup API ────────────────────────────────────────────────────────────────

from pathlib import Path as _Path

@app.post("/api/backup/now")
def trigger_backup(_: User = Depends(require_admin)):
    return backup_svc.backup_now()


@app.get("/api/backup/list")
def list_backups(_: User = Depends(require_admin)):
    backup_dir = _Path(DATA_DIR) / "backups"
    if not backup_dir.exists():
        return []
    files = sorted(backup_dir.glob("restaurant_*.db"), reverse=True)
    return [
        {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)}
        for f in files[:30]
    ]


# ── Thermal printer test endpoint ─────────────────────────────────────────────

class TestPrintBody(BaseModel):
    printer_path: Optional[str] = ""


@app.post("/api/billing/test-print")
def test_thermal_print(body: TestPrintBody, _: User = Depends(require_admin)):
    return printer_svc.test_print(body.printer_path or "")


# ── Change-password endpoint (self) ───────────────────────────────────────────

class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/auth/change-password")
def change_password(body: ChangePasswordBody,
                    current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    from app.utils.security import verify_password
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return RedirectResponse(url="/login")


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.get("/admin")
def admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html")


@app.get("/dashboard")
def dashboard_page(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/menu")
def menu_page(request: Request):
    return templates.TemplateResponse(request, "menu_manage.html")


@app.get("/tables")
def tables_page(request: Request):
    return templates.TemplateResponse(request, "tables.html")


@app.get("/orders")
def orders_page(request: Request):
    return templates.TemplateResponse(request, "orders.html")


@app.get("/kitchen")
def kitchen_page(request: Request):
    return templates.TemplateResponse(request, "kitchen.html")


@app.get("/billing")
def billing_page(request: Request):
    return templates.TemplateResponse(request, "billing.html")


@app.get("/inventory")
def inventory_page(request: Request):
    return templates.TemplateResponse(request, "inventory.html")


@app.get("/users")
def users_page(request: Request):
    return templates.TemplateResponse(request, "users.html")


@app.get("/reports")
def reports_page(request: Request):
    return templates.TemplateResponse(request, "reports.html")


@app.get("/settings")
def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html")


# ── Printable receipt (server-rendered) ───────────────────────────────────────

@app.get("/receipt/{bill_id}")
def receipt_page(bill_id: int, request: Request,
                 token: Optional[str] = None,
                 db: Session = Depends(get_db)):
    """
    Render a print-ready receipt.  Accepts JWT either as a cookie (normal login)
    or as ?token= query param (for opening in a new print window).
    """
    # Resolve token: query param takes priority, then Authorization cookie/header
    raw_token = token
    if not raw_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[7:]
    if not raw_token:
        raw_token = request.cookies.get("access_token", "")

    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Validate JWT
    from app.utils.security import decode_token
    payload = decode_token(raw_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    rid = payload.get("rid")

    # Fetch bill
    q = db.query(Bill).filter(Bill.id == bill_id)
    if rid:
        q = q.filter(Bill.restaurant_id == rid)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Fetch order items for the bill
    from app.routes.billing import _bill_response
    bill_data = _bill_response(bill, db)

    # Fetch restaurant info
    rest = db.query(Restaurant).filter(Restaurant.id == bill.restaurant_id).first()
    rest_data = {
        "name":       rest.name if rest else "",
        "address":    rest.address or "" if rest else "",
        "phone":      rest.phone or "" if rest else "",
        "vat_number": rest.vat_number or "" if rest else "",
    }

    # Fetch per-restaurant receipt settings from AppSettings
    def _setting(key):
        row = db.query(AppSettings).filter(
            AppSettings.restaurant_id == bill.restaurant_id,
            AppSettings.key == key,
        ).first()
        return row.value if row else ""

    receipt_footer = _setting("receipt_footer") or "Thank you for dining with us!"
    receipt_note   = _setting("receipt_note")

    return templates.TemplateResponse(request, "receipt.html", {
        "bill":           bill_data,
        "restaurant":     rest_data,
        "receipt_footer": receipt_footer,
        "receipt_note":   receipt_note,
        "change":         None,
    })
