"""Booking tables."""
from datetime import timedelta

from app.utils import nepal


def at(minutes_from_now):
    when = nepal.now() + timedelta(minutes=minutes_from_now)
    return {"date": when.date().isoformat(), "time": when.strftime("%H:%M")}


def book(client, headers, table_id=None, minutes=180, **kw):
    body = {"customer_name": "Sita", "customer_phone": "9841000001", "party_size": 4,
            "table_id": table_id, **at(minutes), **kw}
    return client.post("/api/reservations", headers=headers, json=body)


def test_booking_shows_on_the_day_list(client, waiter, new_table):
    table = new_table()
    r = book(client, waiter, table["id"], notes="Birthday")
    assert r.status_code == 201, r.text
    res = r.json()
    day = client.get(f"/api/reservations?date={res['date']}", headers=waiter).json()
    assert any(x["id"] == res["id"] and x["table_number"] == table["table_number"] for x in day)


def test_double_booking_the_same_table_is_blocked(client, waiter, new_table):
    table = new_table()
    assert book(client, waiter, table["id"], minutes=300).status_code == 201
    clash = book(client, waiter, table["id"], minutes=330, customer_name="Hari")
    assert clash.status_code == 409 and "already booked" in clash.json()["detail"]
    # Once the first booking's 90 minutes are over the table is free again
    assert book(client, waiter, table["id"], minutes=300 + 95, customer_name="Gita").status_code == 201


def test_availability_suggests_best_fit_first(client, waiter, new_table):
    small, big = new_table(capacity=2), new_table(capacity=6)
    slot = at(240)
    tables = client.get(f"/api/reservations/availability?date={slot['date']}&time={slot['time']}&party_size=2",
                        headers=waiter).json()
    ids = [t["id"] for t in tables]
    assert ids.index(small["id"]) < ids.index(big["id"])
    six = client.get(f"/api/reservations/availability?date={slot['date']}&time={slot['time']}&party_size=6",
                     headers=waiter).json()
    assert next(t for t in six if t["id"] == small["id"])["fits"] is False


def test_booked_table_shows_reserved_on_floor_plan_and_seat_opens_order(client, waiter, new_table):
    table = new_table()
    res = book(client, waiter, table["id"], minutes=20).json()
    card = next(t for t in client.get("/api/tables/overview", headers=waiter).json()["tables"]
                if t["id"] == table["id"])
    assert card["status"] == "reserved" and card["reservation"]["customer_name"] == "Sita"

    seated = client.post(f"/api/reservations/{res['id']}/seat", headers=waiter, json={})
    assert seated.status_code == 200, seated.text
    order = seated.json()["order"]
    assert order["table_id"] == table["id"] and order["guests"] == 4 and order["customer_name"] == "Sita"
    card = next(t for t in client.get("/api/tables/overview", headers=waiter).json()["tables"]
                if t["id"] == table["id"])
    assert card["status"] == "occupied"


def test_seat_without_table_asks_for_one(client, waiter, new_table):
    res = book(client, waiter).json()
    assert client.post(f"/api/reservations/{res['id']}/seat", headers=waiter, json={}).status_code == 400
    table = new_table()
    r = client.post(f"/api/reservations/{res['id']}/seat", headers=waiter, json={"table_id": table["id"]})
    assert r.status_code == 200


def test_cancel_no_show_and_reopen(client, waiter, new_table):
    res = book(client, waiter, new_table()["id"]).json()
    assert client.post(f"/api/reservations/{res['id']}/no-show", headers=waiter).json()["status"] == "no_show"
    assert client.post(f"/api/reservations/{res['id']}/reopen", headers=waiter).json()["status"] == "booked"
    assert client.post(f"/api/reservations/{res['id']}/cancel", headers=waiter).json()["status"] == "cancelled"
    assert client.post(f"/api/reservations/{res['id']}/seat", headers=waiter, json={}).status_code == 400


def test_booking_in_the_past_is_rejected(client, waiter):
    assert book(client, waiter, minutes=-180).status_code == 400


def test_returning_guest_is_remembered_by_phone(client, waiter):
    book(client, waiter, customer_name="Ram Bahadur", customer_phone="98-4100-7777")
    found = client.get("/api/customers/lookup?phone=9841007777", headers=waiter).json()
    assert found["name"] == "Ram Bahadur"


def test_edit_booking_moves_time_and_checks_conflicts(client, waiter, new_table):
    table = new_table()
    a = book(client, waiter, table["id"], minutes=400).json()
    b = book(client, waiter, table["id"], minutes=600, customer_name="Late").json()
    moved = client.put(f"/api/reservations/{b['id']}", headers=waiter, json=at(420))
    assert moved.status_code == 409
    ok = client.put(f"/api/reservations/{b['id']}", headers=waiter, json={**at(700), "party_size": 6})
    assert ok.status_code == 200 and ok.json()["party_size"] == 6
