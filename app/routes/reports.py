"""
Revenue reports and CSV export endpoints.
Timestamps are stored as naive Nepal time (see app.utils.nepal), so date
ranges are plain half-open [start, end) comparisons in NPT.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import Optional, List
import csv
import io
import calendar

from app.database import get_db
from app.models.bill import Bill
from app.models.order import Order, OrderItem
from app.models.menu import MenuItem, Category
from app.models.table import RestaurantTable
from app.models.inventory import Ingredient
from app.models.user import User
from app.models.audit import AuditTrail
from app.routes.auth import require_admin, require_roles
from app.routes.billing import payment_breakdown
from app.utils import nepal

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Sales figures: managers and cashiers; the audit trail: admins only
_report_user = require_roles("admin", "cashier", "superadmin")


# ── Time helpers ──────────────────────────────────────────────────────────────

def _npt_now() -> datetime:
    return nepal.now()


def _to_npt(dt) -> datetime:
    return nepal.to_npt(dt)


def _day_range(d: date) -> tuple:
    return nepal.day_bounds(d)


def _week_range(d: date) -> tuple:
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    days = [monday + timedelta(days=i) for i in range(7)]
    start, _ = _day_range(monday)
    _, end   = _day_range(sunday)
    return start, end, days


def _month_range(year: int, month: int) -> tuple:
    _, last = calendar.monthrange(year, month)
    days = [date(year, month, d) for d in range(1, last + 1)]
    start, _ = _day_range(date(year, month, 1))
    _, end   = _day_range(date(year, month, last))
    return start, end, days


def _fiscal_year_range(fy: str) -> tuple:
    """
    '2081/82' → (start, end, [month_date, ...]) — fiscal year starts July 16.
    """
    try:
        fy_start, fy_end = nepal.fiscal_year_bounds(fy)
    except (ValueError, IndexError):
        raise HTTPException(400, "fy must look like 2083/84")
    # 13 month anchors: mid-July → mid-July covers parts of 13 calendar months
    months = []
    y, m = fy_start.year, 7
    for _ in range(13):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return fy_start, fy_end, months


def _current_fiscal_year() -> str:
    return nepal.fiscal_year()


def _prev_month(year: int, month: int) -> tuple:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _prev_fiscal_year(fy: str) -> str:
    bs = int(fy.split('/')[0]) - 1
    return f"{bs}/{str(bs + 1)[-2:]}"


# ── Query helpers ─────────────────────────────────────────────────────────────

def _bills_in_range(db: Session, restaurant_id, start: datetime, end: datetime):
    q = db.query(Bill).filter(
        Bill.payment_status == "paid",
        Bill.created_at >= start,
        Bill.created_at < end,
    )
    if restaurant_id:
        q = q.filter(Bill.restaurant_id == restaurant_id)
    return q.all()


def _top_items(order_ids: list, db: Session, limit: int = 5) -> list:
    if not order_ids:
        return []
    items = db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids),
                                       OrderItem.kot_status != "void").all()
    agg: dict = {}
    for oi in items:
        if oi.menu_item_id not in agg:
            agg[oi.menu_item_id] = {"qty": 0, "revenue": 0.0}
        agg[oi.menu_item_id]["qty"]     += oi.quantity
        agg[oi.menu_item_id]["revenue"] += round(oi.quantity * oi.unit_price, 2)

    top = sorted(agg.items(), key=lambda x: x[1]["qty"], reverse=True)[:limit]
    result = []
    for mid, data in top:
        mi = db.query(MenuItem).filter(MenuItem.id == mid).first()
        cat_name = None
        if mi:
            cat = db.query(Category).filter(Category.id == mi.category_id).first()
            cat_name = cat.name if cat else None
        result.append({
            "name":     mi.name if mi else "Unknown",
            "category": cat_name,
            "quantity": data["qty"],
            "revenue":  round(data["revenue"], 2),
        })
    return result


def _revenue_stats(bills: list, db: Session, restaurant_id) -> dict:
    if not bills:
        return {
            "total_revenue": 0.0, "total_orders": 0, "avg_order_value": 0.0,
            "total_vat": 0.0, "total_service": 0.0, "total_discount": 0.0,
            "by_payment_method": {}, "by_order_type": {}, "top_items": [],
        }

    total_rev  = round(sum(b.grand_total    or 0 for b in bills), 2)
    total_vat  = round(sum(b.vat_amount     or 0 for b in bills), 2)
    total_svc  = round(sum(b.service_charge or 0 for b in bills), 2)
    total_disc = round(sum(b.discount_amount or 0 for b in bills), 2)
    n = len(bills)
    avg = round(total_rev / n, 2) if n else 0.0

    by_method = payment_breakdown(db, bills)

    order_ids = [b.order_id for b in bills]
    by_type: dict = {}
    if order_ids:
        orders = db.query(Order).filter(Order.id.in_(order_ids)).all()
        rev_map = {b.order_id: (b.grand_total or 0) for b in bills}
        for o in orders:
            ot = o.order_type or "dine_in"
            by_type[ot] = round(by_type.get(ot, 0) + rev_map.get(o.id, 0), 2)

    top = _top_items(order_ids, db)

    return {
        "total_revenue": total_rev,
        "total_orders": n,
        "avg_order_value": avg,
        "total_vat": total_vat,
        "total_service": total_svc,
        "total_discount": total_disc,
        "by_payment_method": by_method,
        "by_order_type": by_type,
        "top_items": top,
    }


def _day_breakdown(bills: list, days: List[date]) -> list:
    rev_map: dict = {}
    cnt_map: dict = {}
    for b in bills:
        d = _to_npt(b.created_at).date() if b.created_at else None
        if d:
            rev_map[d] = round(rev_map.get(d, 0) + (b.grand_total or 0), 2)
            cnt_map[d] = cnt_map.get(d, 0) + 1
    return [
        {"label": d.strftime("%a %d"), "date": str(d),
         "revenue": rev_map.get(d, 0), "orders": cnt_map.get(d, 0)}
        for d in days
    ]


def _hour_breakdown(bills: list, d: date) -> list:
    rev_map = {h: 0.0 for h in range(24)}
    cnt_map = {h: 0   for h in range(24)}
    for b in bills:
        if b.created_at:
            h = _to_npt(b.created_at).hour
            rev_map[h] = round(rev_map[h] + (b.grand_total or 0), 2)
            cnt_map[h] += 1
    return [
        {"label": f"{h:02d}:00", "revenue": rev_map[h], "orders": cnt_map[h]}
        for h in range(24)
    ]


def _month_breakdown(bills: list, months: list) -> list:
    rev_map: dict = {}
    cnt_map: dict = {}
    for b in bills:
        if b.created_at:
            nd = _to_npt(b.created_at).date()
            key = date(nd.year, nd.month, 1)
            rev_map[key] = round(rev_map.get(key, 0) + (b.grand_total or 0), 2)
            cnt_map[key] = cnt_map.get(key, 0) + 1
    return [
        {"label": m.strftime("%b %Y"), "date": str(m),
         "revenue": rev_map.get(m, 0), "orders": cnt_map.get(m, 0)}
        for m in months
    ]


# ── Revenue endpoint ──────────────────────────────────────────────────────────

@router.get("/revenue")
def get_revenue(
    period:   str           = Query("monthly"),
    date_str: Optional[str] = Query(None, alias="date"),   # YYYY-MM-DD
    month:    Optional[int] = Query(None),
    year:     Optional[int] = Query(None),
    fy:       Optional[str] = Query(None),                 # "2081/82"
    db:       Session       = Depends(get_db),
    current_user: User      = Depends(_report_user),
):
    if period not in ("daily", "weekly", "monthly", "yearly"):
        raise HTTPException(400, "period must be daily/weekly/monthly/yearly")

    rid = current_user.restaurant_id
    now = _npt_now()

    if period == "daily":
        d     = date.fromisoformat(date_str) if date_str else now.date()
        start, end = _day_range(d)
        label = d.strftime("%B %d, %Y")
        bills = _bills_in_range(db, rid, start, end)
        breakdown = _hour_breakdown(bills, d)

    elif period == "weekly":
        d     = date.fromisoformat(date_str) if date_str else now.date()
        start, end, days = _week_range(d)
        label = f"Week of {days[0].strftime('%b %d')} – {days[-1].strftime('%b %d, %Y')}"
        bills = _bills_in_range(db, rid, start, end)
        breakdown = _day_breakdown(bills, days)

    elif period == "monthly":
        m = month if month is not None else now.month
        y = year  if year  is not None else now.year
        start, end, days = _month_range(y, m)
        label = date(y, m, 1).strftime("%B %Y")
        bills = _bills_in_range(db, rid, start, end)
        breakdown = _day_breakdown(bills, days)

    else:  # yearly
        current_fy = fy or _current_fiscal_year()
        start, end, months = _fiscal_year_range(current_fy)
        label = f"Fiscal Year {current_fy}"
        bills = _bills_in_range(db, rid, start, end)
        breakdown = _month_breakdown(bills, months)

    stats = _revenue_stats(bills, db, rid)
    return {"period": period, "label": label, "breakdown": breakdown, **stats}


# ── Comparison endpoint ───────────────────────────────────────────────────────

@router.get("/revenue/comparison")
def get_comparison(
    period: str      = Query("monthly"),
    db: Session      = Depends(get_db),
    current_user: User = Depends(_report_user),
):
    rid = current_user.restaurant_id
    now = _npt_now()

    if period == "weekly":
        d = now.date()
        s_cur, e_cur, _ = _week_range(d)
        s_prev, e_prev, _ = _week_range(d - timedelta(days=7))
        cur_label  = "This Week"
        prev_label = "Last Week"

    elif period == "monthly":
        y, m = now.year, now.month
        s_cur, e_cur, _ = _month_range(y, m)
        py, pm = _prev_month(y, m)
        s_prev, e_prev, _ = _month_range(py, pm)
        cur_label  = now.strftime("%B %Y")
        prev_label = date(py, pm, 1).strftime("%B %Y")

    elif period == "yearly":
        fy = _current_fiscal_year()
        s_cur, e_cur, _ = _fiscal_year_range(fy)
        prev_fy = _prev_fiscal_year(fy)
        s_prev, e_prev, _ = _fiscal_year_range(prev_fy)
        cur_label  = f"FY {fy}"
        prev_label = f"FY {prev_fy}"

    else:
        raise HTTPException(400, "period must be weekly/monthly/yearly for comparison")

    cur_bills  = _bills_in_range(db, rid, s_cur,  e_cur)
    prev_bills = _bills_in_range(db, rid, s_prev, e_prev)

    def _pct(cur, prev):
        if prev == 0:
            return None
        return round((cur - prev) / prev * 100, 1)

    cur_rev  = round(sum(b.grand_total or 0 for b in cur_bills),  2)
    prev_rev = round(sum(b.grand_total or 0 for b in prev_bills), 2)

    return {
        "period":           period,
        "current_label":    cur_label,
        "previous_label":   prev_label,
        "current_revenue":  cur_rev,
        "previous_revenue": prev_rev,
        "current_orders":   len(cur_bills),
        "previous_orders":  len(prev_bills),
        "revenue_change_pct": _pct(cur_rev, prev_rev),
        "orders_change_pct":  _pct(len(cur_bills), len(prev_bills)),
    }


# ── CSV helpers ───────────────────────────────────────────────────────────────

def _csv_response(rows: list, headers: list, filename: str) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _parse_date_range(from_str: Optional[str], to_str: Optional[str]):
    now = _npt_now()
    if from_str:
        d_from = date.fromisoformat(from_str)
    else:
        d_from = now.replace(day=1).date()
    if to_str:
        d_to = date.fromisoformat(to_str)
    else:
        d_to = now.date()
    start, _ = _day_range(d_from)
    _, end   = _day_range(d_to)
    return start, end, d_from, d_to


# ── Export: Sales ─────────────────────────────────────────────────────────────

@router.get("/export/sales")
def export_sales(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(_report_user),
):
    start, end, d_from, d_to = _parse_date_range(from_date, to_date)
    rid = current_user.restaurant_id

    q = db.query(Bill).filter(Bill.created_at >= start, Bill.created_at <= end)
    if rid:
        q = q.filter(Bill.restaurant_id == rid)
    bills = q.order_by(Bill.created_at).all()

    rows = []
    for b in bills:
        order = db.query(Order).filter(Order.id == b.order_id).first()
        # Table number
        table_num = ""
        if order and order.table_id:
            tbl = db.query(RestaurantTable).filter(RestaurantTable.id == order.table_id).first()
            if tbl:
                table_num = tbl.table_number
        # Items summary
        ois = db.query(OrderItem).filter(OrderItem.order_id == b.order_id,
                                        OrderItem.kot_status != "void").all()
        items_str = "; ".join(
            f"{oi.quantity}x {db.query(MenuItem).filter(MenuItem.id == oi.menu_item_id).first().name if db.query(MenuItem).filter(MenuItem.id == oi.menu_item_id).first() else '?'}"
            for oi in ois
        )
        # Cashier
        cashier_name = ""
        if b.cashier_id:
            u = db.query(User).filter(User.id == b.cashier_id).first()
            if u:
                cashier_name = u.full_name
        npt_dt = _to_npt(b.created_at)
        rows.append([
            b.bill_number or "",
            npt_dt.strftime("%Y-%m-%d") if npt_dt else "",
            npt_dt.strftime("%H:%M:%S") if npt_dt else "",
            table_num,
            items_str,
            b.subtotal or 0,
            b.discount_amount or 0,
            b.vat_amount or 0,
            b.service_charge or 0,
            b.grand_total or 0,
            b.payment_method or "",
            b.payment_status or "",
            cashier_name,
            b.customer_name or "",
            b.customer_pan or "",
        ])

    filename = f"sales_report_{d_from}_{d_to}.csv"
    return _csv_response(rows, [
        "Bill Number", "Date", "Time", "Table", "Items",
        "Subtotal", "Discount", "VAT", "Service Charge", "Grand Total",
        "Payment Method", "Payment Status", "Cashier",
        "Customer Name", "Customer PAN",
    ], filename)


# ── Export: Item-wise ─────────────────────────────────────────────────────────

@router.get("/export/items")
def export_items(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(_report_user),
):
    start, end, d_from, d_to = _parse_date_range(from_date, to_date)
    rid = current_user.restaurant_id

    q = db.query(Bill).filter(
        Bill.payment_status == "paid",
        Bill.created_at >= start,
        Bill.created_at <= end,
    )
    if rid:
        q = q.filter(Bill.restaurant_id == rid)
    bills = q.all()

    order_ids = [b.order_id for b in bills]
    if not order_ids:
        return _csv_response([], [
            "Item Name", "Category", "Quantity Sold", "Revenue (NPR)",
            "Unit Cost (NPR)", "Total Cost (NPR)", "Profit (NPR)", "Margin %",
        ], f"items_report_{d_from}_{d_to}.csv")

    ois = db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids),
                                     OrderItem.kot_status != "void").all()
    agg: dict = {}  # {menu_item_id: {qty, revenue}}
    for oi in ois:
        if oi.menu_item_id not in agg:
            agg[oi.menu_item_id] = {"qty": 0, "revenue": 0.0}
        agg[oi.menu_item_id]["qty"]     += oi.quantity
        agg[oi.menu_item_id]["revenue"] += oi.quantity * oi.unit_price

    rows = []
    for mid, data in sorted(agg.items(), key=lambda x: x[1]["qty"], reverse=True):
        mi = db.query(MenuItem).filter(MenuItem.id == mid).first()
        if not mi:
            continue
        cat = db.query(Category).filter(Category.id == mi.category_id).first()
        cat_name = cat.name if cat else ""

        # Cost from recipe (sum of ingredient costs)
        from app.models.recipe import RecipeIngredient
        recipe = db.query(RecipeIngredient).filter(RecipeIngredient.menu_item_id == mid).all()
        unit_cost = 0.0
        for r in recipe:
            ing = db.query(Ingredient).filter(Ingredient.id == r.ingredient_id).first()
            if ing:
                unit_cost += r.quantity_used * ing.cost_per_unit
        total_cost = round(unit_cost * data["qty"], 2)
        revenue    = round(data["revenue"], 2)
        profit     = round(revenue - total_cost, 2)
        margin     = round(profit / revenue * 100, 1) if revenue > 0 else 0.0

        rows.append([
            mi.name, cat_name, data["qty"], revenue,
            round(unit_cost, 2), total_cost, profit, margin,
        ])

    return _csv_response(rows, [
        "Item Name", "Category", "Quantity Sold", "Revenue (NPR)",
        "Unit Cost (NPR)", "Total Cost (NPR)", "Profit (NPR)", "Margin %",
    ], f"items_report_{d_from}_{d_to}.csv")


# ── Export: Inventory ─────────────────────────────────────────────────────────

@router.get("/export/inventory")
def export_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(_report_user),
):
    rid = current_user.restaurant_id
    q = db.query(Ingredient)
    if rid:
        q = q.filter(Ingredient.restaurant_id == rid)
    ings = q.order_by(Ingredient.name).all()

    rows = []
    for ing in ings:
        total_val = round(ing.current_stock * ing.cost_per_unit, 2)
        status = "OK"
        if ing.current_stock <= 0:
            status = "Out of Stock"
        elif ing.current_stock <= ing.minimum_stock:
            status = "Low Stock"
        rows.append([
            ing.name, ing.unit,
            ing.current_stock, ing.minimum_stock,
            ing.cost_per_unit, total_val,
            ing.supplier_name or "",
            status,
            ing.last_purchased_at.strftime("%Y-%m-%d") if ing.last_purchased_at else "",
        ])

    now_str = _npt_now().strftime("%Y-%m-%d")
    return _csv_response(rows, [
        "Ingredient", "Unit", "Current Stock", "Minimum Stock",
        "Cost Per Unit (NPR)", "Total Value (NPR)",
        "Supplier", "Status", "Last Purchased",
    ], f"inventory_{now_str}.csv")


# ── Export: VAT (Schedule-8 IRD format) ──────────────────────────────────────

@router.get("/export/vat")
def export_vat(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(_report_user),
):
    start, end, d_from, d_to = _parse_date_range(from_date, to_date)
    rid = current_user.restaurant_id

    q = db.query(Bill).filter(
        Bill.payment_status == "paid",
        Bill.vat_amount > 0,
        Bill.created_at >= start,
        Bill.created_at <= end,
    )
    if rid:
        q = q.filter(Bill.restaurant_id == rid)
    bills = q.order_by(Bill.created_at).all()

    rows = []
    for i, b in enumerate(bills, 1):
        npt_dt = _to_npt(b.created_at)
        rows.append([
            i,                                                    # Serial No.
            npt_dt.strftime("%Y-%m-%d") if npt_dt else "",       # Date
            b.bill_number or "",                                  # Bill/Voucher No.
            b.customer_pan or "",                                 # Buyer PAN
            b.customer_name or "",                                # Buyer Name
            b.taxable_amount or 0,                               # Taxable Amount
            b.vat_amount or 0,                                   # VAT Amount
            b.grand_total or 0,                                  # Total Amount
            b.fiscal_year or "",                                  # Fiscal Year
        ])

    total_taxable = round(sum(b.taxable_amount or 0 for b in bills), 2)
    total_vat     = round(sum(b.vat_amount     or 0 for b in bills), 2)
    total_grand   = round(sum(b.grand_total    or 0 for b in bills), 2)
    rows.append(["", "", "", "", "TOTAL", total_taxable, total_vat, total_grand, ""])

    return _csv_response(rows, [
        "S.N.", "Date", "Bill/Voucher No.", "Buyer PAN", "Buyer Name",
        "Taxable Amount (NPR)", "VAT (NPR)", "Total Amount (NPR)", "Fiscal Year",
    ], f"vat_report_{d_from}_{d_to}.csv")


# ── Export: Audit Trail ───────────────────────────────────────────────────────

@router.get("/export/audit")
def export_audit(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    start, end, d_from, d_to = _parse_date_range(from_date, to_date)
    rid = current_user.restaurant_id

    q = db.query(AuditTrail).filter(
        AuditTrail.created_at >= start,
        AuditTrail.created_at <= end,
    )
    if rid:
        q = q.filter(AuditTrail.restaurant_id == rid)
    logs = q.order_by(AuditTrail.created_at).all()

    rows = []
    for log in logs:
        actor_name = ""
        if log.user_id:
            u = db.query(User).filter(User.id == log.user_id).first()
            if u:
                actor_name = f"{u.full_name} ({u.username})"
        npt_dt = _to_npt(log.created_at)
        rows.append([
            npt_dt.strftime("%Y-%m-%d %H:%M:%S") if npt_dt else "",
            actor_name,
            log.action or "",
            log.table_name or "",
            log.record_id or "",
            log.old_value or "",
            log.new_value or "",
            log.reason or "",
            log.ip_address or "",
        ])

    return _csv_response(rows, [
        "Timestamp (NPT)", "User", "Action", "Table", "Record ID",
        "Old Value", "New Value", "Reason", "IP Address",
    ], f"audit_trail_{d_from}_{d_to}.csv")
