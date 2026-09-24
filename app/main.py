import io
import os
import logging
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import APP_NAME, APP_VERSION, BACKUP_ENABLED
from app.database import create_tables, SessionLocal, get_db
import app.models  # noqa: F401 — registers all models with SQLAlchemy metadata
from app.models.restaurant import Restaurant
from app.models.user import User
from app.models.bill import Bill
from app.models.menu import Category, MenuItem
from app.models.order import Order, OrderItem
from app.models.table import RestaurantTable
from app.utils import nepal
from app.utils.security import decode_token, hash_password
from app.routes import (auth, menu, tables, orders, kitchen, billing, inventory,
                        restaurants, users, reports, reservations, customers)
from app.routes import settings as settings_router
from app.routes.auth import get_current_user, require_admin, token_from_request
from app.services import backup as backup_svc
from app.services import demo_data
from app.services import printer as printer_svc
from app.services.billing_calc import compute_totals, order_lines, validate_discount
from app.services.restaurant_settings import get_setting, printer_path, tax_config

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
app.include_router(reservations.router)
app.include_router(customers.router)


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    create_tables()
    _seed()
    if BACKUP_ENABLED:
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
            # Brand-new install only: sample menu, tables and staff so every screen works on day one
            demo_data.populate(db, demo.id)
            db.commit()
            _log.info("Demo restaurant created → code: demo / username: admin / password: admin123")
    finally:
        db.close()


# ── Backup API ────────────────────────────────────────────────────────────────

@app.post("/api/backup/now")
def trigger_backup(_: User = Depends(require_admin)):
    return backup_svc.backup_now()


@app.get("/api/backup/list")
def list_backups(_: User = Depends(require_admin)):
    return backup_svc.list_backups()


# ── Thermal printer test endpoint ─────────────────────────────────────────────

class TestPrintBody(BaseModel):
    printer_path: Optional[str] = ""


@app.post("/api/billing/test-print")
def test_thermal_print(body: TestPrintBody, current_user: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    path = (body.printer_path or "").strip() or printer_path(db, current_user.restaurant_id)
    return printer_svc.test_print(path)


# ── QR image (payment QR, device-connect link) — generated locally, works offline ──

@app.get("/api/qr.png")
def qr_png(data: str = Query(..., max_length=2000), _: User = Depends(get_current_user)):
    import qrcode
    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "private, max-age=3600"})


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


_FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<text y=".9em" font-size="90">🍽️</text></svg>')


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(content=_FAVICON, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


def _page(name: str):
    def handler(request: Request):
        return templates.TemplateResponse(request, name)
    return handler


for _path, _template in {
    "/login":        "login.html",
    "/register":     "register.html",
    "/admin":        "admin.html",
    "/dashboard":    "dashboard.html",
    "/menu":         "menu_manage.html",
    "/tables":       "tables.html",
    "/orders":       "orders.html",
    "/kitchen":      "kitchen.html",
    "/billing":      "billing.html",
    "/reservations": "reservations.html",
    "/inventory":    "inventory.html",
    "/users":        "users.html",
    "/reports":      "reports.html",
    "/settings":     "settings.html",
}.items():
    app.add_api_route(_path, _page(_template), methods=["GET"], include_in_schema=False)


# ── Printable pages (server-rendered, 80mm thermal friendly) ──────────────────

def _page_user(request: Request, token: Optional[str], db: Session) -> User:
    """Print pages open in a new window/iframe: accept ?token=, the Bearer header,
    or the login cookie."""
    raw_token = token or token_from_request(request)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(raw_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == int(payload.get("sub"))).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def _restaurant_info(db: Session, restaurant_id: int) -> dict:
    rest = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    return {
        "name":       rest.name if rest else "",
        "address":    (rest.address or "") if rest else "",
        "phone":      (rest.phone or "") if rest else "",
        "vat_number": (rest.vat_number or "") if rest else "",
    }


@app.get("/receipt/{bill_id}", include_in_schema=False)
def receipt_page(bill_id: int, request: Request,
                 token: Optional[str] = None,
                 db: Session = Depends(get_db)):
    """Print-ready tax invoice.  Reprints are labelled "COPY OF ORIGINAL - N" (IRD)."""
    user = _page_user(request, token, db)
    q = db.query(Bill).filter(Bill.id == bill_id)
    if user.restaurant_id:
        q = q.filter(Bill.restaurant_id == user.restaurant_id)
    bill = q.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill_data = billing._bill_response(bill, db)
    return templates.TemplateResponse(request, "receipt.html", {
        "bill":           bill_data,
        "restaurant":     _restaurant_info(db, bill.restaurant_id),
        "receipt_footer": get_setting(db, bill.restaurant_id, "receipt_footer")
                          or "Thank you for dining with us!",
        "receipt_note":   get_setting(db, bill.restaurant_id, "receipt_note") or "",
        "copy_number":    max(0, (bill.print_count or 0) - 1),
    })


@app.get("/kot-print/{order_id}/{kot_number}", include_in_schema=False)
def kot_print_page(order_id: int, kot_number: int, request: Request,
                   token: Optional[str] = None, db: Session = Depends(get_db)):
    """Kitchen/bar ticket slips for one KOT — one slip per station."""
    user = _page_user(request, token, db)
    q = db.query(Order).filter(Order.id == order_id)
    if user.restaurant_id:
        q = q.filter(Order.restaurant_id == user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    rows = (db.query(OrderItem, MenuItem, Category)
              .outerjoin(MenuItem, MenuItem.id == OrderItem.menu_item_id)
              .outerjoin(Category, Category.id == MenuItem.category_id)
              .filter(OrderItem.order_id == order.id, OrderItem.kot_number == kot_number,
                      OrderItem.kot_status != "void")
              .order_by(OrderItem.id).all())
    if not rows:
        raise HTTPException(status_code=404, detail="Ticket not found")
    slips: dict[str, list] = {}
    for oi, mi, cat in rows:
        station = (cat.station if cat and cat.station else "kitchen")
        slips.setdefault(station, []).append(
            {"name": mi.name if mi else "Unknown", "quantity": oi.quantity, "notes": oi.notes})
    table = db.get(RestaurantTable, order.table_id) if order.table_id else None
    waiter = db.get(User, order.waiter_id) if order.waiter_id else None
    sent_at = nepal.to_npt(rows[0][0].kot_sent_at)
    return templates.TemplateResponse(request, "kot_print.html", {
        "restaurant": _restaurant_info(db, order.restaurant_id),
        "order": order,
        "table_number": table.table_number if table else None,
        "waiter_name": waiter.full_name if waiter else None,
        "kot_number": kot_number,
        "sent_at": sent_at.strftime("%Y-%m-%d %H:%M") if sent_at else "",
        "slips": slips,
    })


@app.get("/check/{order_id}", include_in_schema=False)
def check_page(order_id: int, request: Request, token: Optional[str] = None,
               discount_type: Optional[str] = None, discount_value: float = 0.0,
               service: int = 1, db: Session = Depends(get_db)):
    """Pre-bill ("check") for the guest to review before paying — not a tax invoice."""
    user = _page_user(request, token, db)
    q = db.query(Order).filter(Order.id == order_id)
    if user.restaurant_id:
        q = q.filter(Order.restaurant_id == user.restaurant_id)
    order = q.first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    discount_type = validate_discount(discount_type, discount_value)
    lines = order_lines(db, order.id)
    totals = compute_totals(lines, discount_type, discount_value, bool(service),
                            tax_config(db, order.restaurant_id))
    table = db.get(RestaurantTable, order.table_id) if order.table_id else None
    return templates.TemplateResponse(request, "check.html", {
        "restaurant": _restaurant_info(db, order.restaurant_id),
        "order": order,
        "table_number": table.table_number if table else None,
        "lines": lines,
        "totals": totals,
        "printed_at": nepal.now().strftime("%Y-%m-%d %H:%M"),
    })
