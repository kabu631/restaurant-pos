"""
Table bookings.  A booked table shows as "reserved" on the floor plan from an
hour before the booking (Settings → reservation_hold_minutes); "Seat" turns the
booking into an open order on that table in one tap.
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, db_transaction
from app.models.order import Order
from app.models.reservation import Reservation
from app.models.table import RestaurantTable
from app.models.user import User
from app.services.permissions import require_perm
from app.routes.auth import get_current_user
from app.routes.tables import natural_key
from app.services import order_ops as ops
from app.services.customers import upsert_customer
from app.utils import nepal

router = APIRouter(prefix="/api/reservations", tags=["reservations"])

STATUSES = {"booked", "seated", "cancelled", "no_show"}
_LATE_AFTER = timedelta(minutes=15)


# --- Schemas ---

class ReservationIn(BaseModel):
    customer_name: str
    customer_phone: Optional[str] = None
    party_size: int = 2
    date: str                      # YYYY-MM-DD (Nepal)
    time: str                      # HH:MM, 24h
    duration_min: int = 90
    table_id: Optional[int] = None
    notes: Optional[str] = None

class ReservationUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    party_size: Optional[int] = None
    date: Optional[str] = None
    time: Optional[str] = None
    duration_min: Optional[int] = None
    table_id: Optional[int] = None
    notes: Optional[str] = None

class SeatBody(BaseModel):
    table_id: Optional[int] = None


# --- Helpers ---

def _parse_when(date_str: str, time_str: str) -> datetime:
    try:
        return datetime.combine(date.fromisoformat(date_str),
                                datetime.strptime(time_str.strip()[:5], "%H:%M").time())
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Use date YYYY-MM-DD and time HH:MM")


def _validate(party_size: int, duration_min: int, name: str):
    if not (name or "").strip():
        raise HTTPException(status_code=400, detail="Guest name is required")
    if not 1 <= party_size <= 200:
        raise HTTPException(status_code=400, detail="Party size must be between 1 and 200")
    if not 15 <= duration_min <= 720:
        raise HTTPException(status_code=400, detail="Duration must be 15 minutes to 12 hours")


def _get(db: Session, reservation_id: int, user: User) -> Reservation:
    r = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.restaurant_id == ops.restaurant_id_of(user),
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Booking not found")
    return r


def _table(db: Session, restaurant_id: int, table_id: int) -> RestaurantTable:
    t = db.query(RestaurantTable).filter(RestaurantTable.id == table_id,
                                         RestaurantTable.restaurant_id == restaurant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Table not found")
    return t


def _overlapping(db: Session, restaurant_id: int, table_id: int, start: datetime,
                 duration_min: int, exclude_id: Optional[int] = None) -> Optional[Reservation]:
    """First booked reservation on the table whose time window overlaps [start, start+duration)."""
    end = start + timedelta(minutes=duration_min)
    q = db.query(Reservation).filter(
        Reservation.restaurant_id == restaurant_id,
        Reservation.table_id == table_id,
        Reservation.status == "booked",
        Reservation.reserved_for < end,
        Reservation.reserved_for > start - timedelta(hours=12),
    )
    if exclude_id:
        q = q.filter(Reservation.id != exclude_id)
    for r in q.all():
        if start < r.reserved_for + timedelta(minutes=r.duration_min or 90):
            return r
    return None


def _check_table_free(db: Session, restaurant_id: int, table_id: Optional[int], start: datetime,
                      duration_min: int, exclude_id: Optional[int] = None):
    if not table_id:
        return
    table = _table(db, restaurant_id, table_id)
    clash = _overlapping(db, restaurant_id, table_id, start, duration_min, exclude_id)
    if clash:
        end = clash.reserved_for + timedelta(minutes=clash.duration_min or 90)
        raise HTTPException(
            status_code=409,
            detail=(f"Table {table.table_number} is already booked "
                    f"{clash.reserved_for:%I:%M %p}–{end:%I:%M %p} for {clash.customer_name}"),
        )


def _out(r: Reservation, tables: dict) -> dict:
    when = nepal.to_npt(r.reserved_for)
    return {
        "id": r.id,
        "customer_name": r.customer_name,
        "customer_phone": r.customer_phone,
        "party_size": r.party_size,
        "reserved_for": nepal.iso(r.reserved_for),
        "date": when.date().isoformat(),
        "time": when.strftime("%H:%M"),
        "duration_min": r.duration_min,
        "table_id": r.table_id,
        "table_number": tables.get(r.table_id),
        "status": r.status,
        "notes": r.notes,
        "order_id": r.order_id,
        "is_late": r.status == "booked" and nepal.now() > when + _LATE_AFTER,
        "created_at": nepal.iso(r.created_at),
    }


def _table_names(db: Session, restaurant_id: int) -> dict:
    return {t.id: t.table_number for t in
            db.query(RestaurantTable).filter(RestaurantTable.restaurant_id == restaurant_id).all()}


# --- Endpoints ---

@router.get("")
def list_reservations(date_str: Optional[str] = Query(None, alias="date"), days: int = 1,
                      status_filter: Optional[str] = None,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    """Bookings for a day (default today, Nepal time), or several days with ?days=."""
    rid = ops.restaurant_id_of(current_user)
    try:
        day = date.fromisoformat(date_str) if date_str else nepal.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    start, _ = nepal.day_bounds(day)
    end = start + timedelta(days=max(1, min(days, 62)))
    q = db.query(Reservation).filter(Reservation.restaurant_id == rid,
                                     Reservation.reserved_for >= start,
                                     Reservation.reserved_for < end)
    if status_filter:
        q = q.filter(Reservation.status == status_filter)
    tables = _table_names(db, rid)
    return [_out(r, tables) for r in q.order_by(Reservation.reserved_for, Reservation.id).all()]


@router.get("/availability")
def availability(date_str: str = Query(..., alias="date"), time: str = Query(...),
                 party_size: int = 2, duration_min: int = 90,
                 exclude_id: Optional[int] = None,
                 db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Tables for a booking, best fit first: free ones that seat the party with the fewest spare seats."""
    rid = ops.restaurant_id_of(current_user)
    start = _parse_when(date_str, time)
    soon = start - nepal.now() < timedelta(hours=2)
    busy_tables = {o.table_id for o in db.query(Order).filter(
        Order.restaurant_id == rid, Order.status == "active", Order.table_id.isnot(None)).all()}
    result = []
    for t in db.query(RestaurantTable).filter(RestaurantTable.restaurant_id == rid).all():
        clash = _overlapping(db, rid, t.id, start, duration_min, exclude_id)
        result.append({
            "id": t.id,
            "table_number": t.table_number,
            "capacity": t.capacity,
            "floor": t.floor or "Ground",
            "fits": t.capacity >= party_size,
            "available": clash is None,
            "clash": f"Booked {clash.reserved_for:%I:%M %p} · {clash.customer_name}" if clash else None,
            "occupied_now": soon and t.id in busy_tables,
        })
    result.sort(key=lambda t: (not t["available"], not t["fits"],
                               t["capacity"] - party_size if t["fits"] else 0,
                               natural_key(t["table_number"])))
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_reservation(body: ReservationIn, db: Session = Depends(get_db),
                       current_user: User = Depends(require_perm("bookings.manage"))):
    rid = ops.restaurant_id_of(current_user)
    _validate(body.party_size, body.duration_min, body.customer_name)
    when = _parse_when(body.date, body.time)
    if when < nepal.now() - timedelta(hours=1):
        raise HTTPException(status_code=400, detail="That time has already passed")
    _check_table_free(db, rid, body.table_id, when, body.duration_min)

    r = Reservation(
        restaurant_id=rid,
        table_id=body.table_id,
        customer_name=body.customer_name.strip(),
        customer_phone=(body.customer_phone or "").strip() or None,
        party_size=body.party_size,
        reserved_for=when,
        duration_min=body.duration_min,
        notes=(body.notes or "").strip() or None,
        status="booked",
        created_by=current_user.id,
    )
    db.add(r)
    upsert_customer(db, rid, r.customer_name, r.customer_phone)
    db.commit()
    db.refresh(r)
    return _out(r, _table_names(db, rid))


@router.put("/{reservation_id}")
def update_reservation(reservation_id: int, body: ReservationUpdate,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(require_perm("bookings.manage"))):
    r = _get(db, reservation_id, current_user)
    if r.status != "booked":
        raise HTTPException(status_code=400, detail=f"This booking is already {r.status.replace('_', ' ')}")
    data = body.model_dump(exclude_unset=True)
    when = nepal.to_npt(r.reserved_for)
    if "date" in data or "time" in data:
        when = _parse_when(data.get("date") or when.date().isoformat(),
                           data.get("time") or when.strftime("%H:%M"))
    name = data.get("customer_name", r.customer_name)
    party = data.get("party_size", r.party_size)
    duration = data.get("duration_min", r.duration_min or 90)
    table_id = data["table_id"] if "table_id" in data else r.table_id
    _validate(party, duration, name)
    _check_table_free(db, r.restaurant_id, table_id, when, duration, exclude_id=r.id)

    r.customer_name = name.strip()
    if "customer_phone" in data:
        r.customer_phone = (data["customer_phone"] or "").strip() or None
    r.party_size = party
    r.duration_min = duration
    r.reserved_for = when
    r.table_id = table_id
    if "notes" in data:
        r.notes = (data["notes"] or "").strip() or None
    upsert_customer(db, r.restaurant_id, r.customer_name, r.customer_phone)
    db.commit()
    return _out(r, _table_names(db, r.restaurant_id))


@router.post("/{reservation_id}/seat")
def seat_reservation(reservation_id: int, body: SeatBody, db: Session = Depends(get_db),
                     current_user: User = Depends(require_perm("bookings.manage"))):
    """Guests arrived: open an order on the booked (or chosen) table."""
    r = _get(db, reservation_id, current_user)
    if r.status != "booked":
        raise HTTPException(status_code=400, detail=f"This booking is already {r.status.replace('_', ' ')}")
    table_id = body.table_id or r.table_id
    if not table_id:
        raise HTTPException(status_code=400, detail="Choose a table to seat this party")
    table = _table(db, r.restaurant_id, table_id)
    busy = ops.active_order_for_table(db, table.id)
    if busy:
        raise HTTPException(status_code=409,
                            detail=f"Table {table.table_number} still has an open order (#{busy.id})")

    with db_transaction(db):
        order = Order(
            restaurant_id=r.restaurant_id,
            order_type="dine_in",
            table_id=table.id,
            guests=r.party_size,
            customer_name=r.customer_name,
            customer_phone=r.customer_phone,
            notes=r.notes,
            waiter_id=current_user.id,
            status="active",
        )
        db.add(order)
        db.flush()
        table.status = "occupied"
        r.status = "seated"
        r.table_id = table.id
        r.order_id = order.id
        db.commit()
        db.refresh(order)

    return {"reservation": _out(r, _table_names(db, r.restaurant_id)),
            "order": ops.order_detail(db, order)}


def _set_status(db: Session, r: Reservation, new_status: str, allowed_from: tuple) -> dict:
    if r.status not in allowed_from:
        raise HTTPException(status_code=400, detail=f"This booking is {r.status.replace('_', ' ')}")
    if new_status == "booked":
        _check_table_free(db, r.restaurant_id, r.table_id, nepal.to_npt(r.reserved_for),
                          r.duration_min or 90, exclude_id=r.id)
    r.status = new_status
    db.commit()
    return _out(r, _table_names(db, r.restaurant_id))


@router.post("/{reservation_id}/cancel")
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(require_perm("bookings.manage"))):
    return _set_status(db, _get(db, reservation_id, current_user), "cancelled", ("booked",))


@router.post("/{reservation_id}/no-show")
def no_show(reservation_id: int, db: Session = Depends(get_db),
            current_user: User = Depends(require_perm("bookings.manage"))):
    return _set_status(db, _get(db, reservation_id, current_user), "no_show", ("booked",))


@router.post("/{reservation_id}/reopen")
def reopen_reservation(reservation_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(require_perm("bookings.manage"))):
    """Undo a cancel / no-show."""
    return _set_status(db, _get(db, reservation_id, current_user), "booked",
                       ("cancelled", "no_show"))
