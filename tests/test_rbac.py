"""
Role-based access: waiter takes orders, kitchen accepts them, cashier bills and takes
payment, and the admin can do everything — including changing what the others may do.

Runs in its own restaurant so permission changes and sign-outs never affect other tests.
"""
import uuid

import pytest

from tests.conftest import _login


@pytest.fixture(scope="module")
def shop(client):
    code = f"rb{uuid.uuid4().hex[:8]}"
    r = client.post("/api/restaurants/register", json={
        "restaurant_name": "RBAC Place", "restaurant_code": code,
        "admin_username": "owner", "admin_password": "owner123", "admin_full_name": "Owner",
    })
    assert r.status_code == 201, r.text
    admin = _login(client, "owner", "owner123", code)
    # the owner's PIN approves discounts and voids
    me = client.get("/api/auth/me", headers=admin).json()
    assert client.patch(f"/api/users/{me['id']}/reset-pin", headers=admin,
                        json={"new_pin": "9090"}).status_code == 200

    cat = client.post("/api/menu/categories", headers=admin, json={"name": "Mains"}).json()
    item = client.post("/api/menu/items", headers=admin,
                       json={"category_id": cat["id"], "name": "Dal Bhat", "price": 500}).json()
    staff = {}
    for role, pin in (("waiter", "1201"), ("cashier", "1202"), ("kitchen", "1203")):
        r = client.post("/api/users", headers=admin, json={
            "full_name": f"{role.title()} One", "username": f"{role}x", "password": "pass123",
            "role": role, "pin": pin})
        assert r.status_code == 201, r.text
        staff[role] = _login(client, f"{role}x", "pass123", code)
    return {"code": code, "admin": admin, "item": item, **staff}


def _table(client, shop):
    r = client.post("/api/tables", headers=shop["admin"], json={
        "table_number": f"T-{uuid.uuid4().hex[:5]}", "capacity": 4})
    assert r.status_code == 201, r.text
    return r.json()


def _order(client, shop, who="waiter", send=True):
    r = client.post("/api/orders", headers=shop[who], json={
        "table_id": _table(client, shop)["id"], "guests": 2, "send_kot": send,
        "items": [{"menu_item_id": shop["item"]["id"], "quantity": 2}]})
    assert r.status_code == 201, r.text
    return r.json()


def _checkout(client, shop, order_id, who="cashier", **extra):
    return client.post("/api/billing/checkout", headers=shop[who], json={
        "order_id": order_id, "payments": [{"method": "cash"}], **extra})


def test_me_lists_permissions_per_role(client, shop):
    me = {r: client.get("/api/auth/me", headers=shop[r]).json() for r in
          ("admin", "waiter", "cashier", "kitchen")}
    assert "billing.void" in me["admin"]["permissions"]
    assert "orders.take" in me["waiter"]["permissions"]
    assert "billing.pay" not in me["waiter"]["permissions"]
    assert "billing.pay" in me["cashier"]["permissions"]
    assert me["kitchen"]["permissions"] == ["kitchen.manage", "menu.availability"]
    assert me["cashier"]["discount_limit"] == 10


def test_restaurant_flow_each_role_does_its_own_job(client, shop):
    order = _order(client, shop)                            # waiter takes the order
    # the waiter can't take payment, the kitchen can't take orders
    assert _checkout(client, shop, order["id"], who="waiter").status_code == 403
    assert client.post("/api/orders", headers=shop["kitchen"], json={
        "order_type": "takeaway", "items": []}).status_code == 403
    # the kitchen accepts the ticket; a waiter can't press kitchen buttons
    kot = order["kot"]["kot_number"] if isinstance(order.get("kot"), dict) else order["items"][0]["kot_number"]
    url = f"/api/kitchen/tickets/{order['id']}/{kot}/advance"
    assert client.patch(url, headers=shop["waiter"]).status_code == 403
    r = client.patch(url, headers=shop["kitchen"])
    assert r.status_code == 200 and r.json()["kot_status"] == "preparing"
    # the kitchen can't bill
    assert _checkout(client, shop, order["id"], who="kitchen").status_code == 403
    # the cashier takes payment and prints
    r = _checkout(client, shop, order["id"])
    assert r.status_code == 200, r.text
    bill = r.json()
    assert client.patch(f"/api/billing/bills/{bill['id']}/print",
                        headers=shop["cashier"]).status_code == 200


def test_denied_message_is_friendly(client, shop):
    r = client.get("/api/reports/revenue?period=daily", headers=shop["waiter"])
    assert r.status_code == 403
    assert "Waiter" in r.json()["detail"] and "admin" in r.json()["detail"]


def test_kitchen_marks_dish_sold_out_and_it_is_audited(client, shop):
    item = shop["item"]["id"]
    assert client.patch(f"/api/menu/items/{item}/toggle", headers=shop["waiter"]).status_code == 403
    assert client.patch(f"/api/menu/items/{item}/toggle", headers=shop["kitchen"]).json()["is_available"] is False
    assert client.patch(f"/api/menu/items/{item}/toggle", headers=shop["kitchen"]).json()["is_available"] is True
    log = client.get("/api/activity", headers=shop["admin"]).json()["entries"]
    assert any(e["action"] == "SOLD_OUT" and "Dal Bhat" in e["text"] for e in log)


def test_discount_above_limit_needs_admin_pin(client, shop):
    order = _order(client, shop)
    r = _checkout(client, shop, order["id"], discount_type="percentage", discount_value=25)
    assert r.status_code == 403 and r.headers.get("X-Needs-Override") == "1"
    r = _checkout(client, shop, order["id"], discount_type="percentage", discount_value=25,
                  override_pin="1202")     # the cashier's own PIN is not an admin PIN
    assert r.status_code == 403
    r = _checkout(client, shop, order["id"], discount_type="percentage", discount_value=25,
                  override_pin="9090")
    assert r.status_code == 200, r.text
    log = client.get("/api/activity?category=billing", headers=shop["admin"]).json()["entries"]
    assert any("approved by Owner" in e["text"] for e in log)


def test_discount_within_limit_is_fine(client, shop):
    order = _order(client, shop)
    r = _checkout(client, shop, order["id"], discount_type="percentage", discount_value=10)
    assert r.status_code == 200, r.text


def test_cashier_void_needs_admin_pin(client, shop):
    bill = _checkout(client, shop, _order(client, shop)["id"]).json()
    url = f"/api/billing/bills/{bill['id']}/void"
    r = client.post(url, headers=shop["cashier"], json={"reason": "Wrong table"})
    assert r.status_code == 403 and r.headers.get("X-Needs-Override") == "1"
    r = client.post(url, headers=shop["cashier"], json={"reason": "Wrong table", "override_pin": "9090"})
    assert r.status_code == 200 and r.json()["payment_status"] == "void"


def test_admin_changes_role_permissions(client, shop):
    admin = shop["admin"]
    cat = client.get("/api/permissions", headers=admin).json()
    assert {r["key"] for r in cat["roles"]} == {"cashier", "waiter", "kitchen"}
    assert client.get("/api/permissions", headers=shop["cashier"]).status_code == 403
    # let waiters take payment too (small restaurant), and raise the discount limit
    waiter = next(r for r in cat["roles"] if r["key"] == "waiter")
    r = client.put("/api/permissions", headers=admin, json={
        "grants": {"waiter": waiter["grants"] + ["billing.pay"]}, "max_discount_pct": 20})
    assert r.status_code == 200, r.text
    try:
        order = _order(client, shop)
        assert _checkout(client, shop, order["id"], who="waiter").status_code == 200
        assert client.get("/api/auth/me", headers=shop["cashier"]).json()["discount_limit"] == 20
    finally:
        client.put("/api/permissions", headers=admin,
                   json={"grants": {"waiter": waiter["defaults"]}, "max_discount_pct": 10})
    assert _checkout(client, shop, _order(client, shop)["id"], who="waiter").status_code == 403
    # the admin's own powers can't be edited
    assert client.put("/api/permissions", headers=admin,
                      json={"grants": {"admin": []}}).status_code == 400
    assert client.put("/api/permissions", headers=admin,
                      json={"grants": {"waiter": ["fly.plane"]}}).status_code == 400


def test_admin_signs_staff_out_everywhere(client, shop):
    admin = shop["admin"]
    r = client.post("/api/users", headers=admin, json={
        "full_name": "Temp Waiter", "username": "tempw", "password": "pass123", "role": "waiter"})
    uid = r.json()["id"]
    h = _login(client, "tempw", "pass123", shop["code"])
    assert client.get("/api/auth/me", headers=h).status_code == 200
    staff = {u["id"]: u for u in client.get("/api/users", headers=admin).json()}
    assert staff[uid]["online"] is True
    assert client.post(f"/api/users/{uid}/sign-out", headers=admin).status_code == 200
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 401 and "signed out" in r.json()["detail"]
    # logging in again works; deactivating signs out too
    h = _login(client, "tempw", "pass123", shop["code"])
    client.patch(f"/api/users/{uid}/deactivate", headers=admin)
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_role_change_ends_old_session(client, shop):
    admin = shop["admin"]
    uid = client.post("/api/users", headers=admin, json={
        "full_name": "Promo", "username": "promo", "password": "pass123", "role": "waiter"}).json()["id"]
    h = _login(client, "promo", "pass123", shop["code"])
    client.put(f"/api/users/{uid}", headers=admin, json={"role": "cashier"})
    assert client.get("/api/auth/me", headers=h).status_code == 401
    h = _login(client, "promo", "pass123", shop["code"])
    assert "billing.pay" in client.get("/api/auth/me", headers=h).json()["permissions"]


def test_login_hours(client, shop):
    admin = shop["admin"]
    uid = client.post("/api/users", headers=admin, json={
        "full_name": "Night", "username": "night", "password": "pass123", "role": "kitchen",
        "shift_start": "00:00", "shift_end": "00:01"}).json()["id"]
    from app.routes.auth import within_shift
    from app.models.user import User
    u = User(role="kitchen", shift_start="18:00", shift_end="02:00")
    from datetime import datetime
    assert within_shift(u, datetime(2026, 1, 1, 23, 0))
    assert within_shift(u, datetime(2026, 1, 1, 1, 30))
    assert not within_shift(u, datetime(2026, 1, 1, 12, 0))
    # bad times are rejected; clearing the hours allows login at any time
    assert client.put(f"/api/users/{uid}", headers=admin,
                      json={"shift_start": "25:00", "shift_end": "02:00"}).status_code == 400
    assert client.put(f"/api/users/{uid}", headers=admin,
                      json={"shift_start": "", "shift_end": ""}).status_code == 200
    _login(client, "night", "pass123", shop["code"])


def test_only_admin_cannot_be_demoted_or_deactivated(client, shop):
    admin = shop["admin"]
    me = client.get("/api/auth/me", headers=admin).json()
    assert client.put(f"/api/users/{me['id']}", headers=admin,
                      json={"role": "cashier"}).status_code == 400
    assert client.get("/api/users", headers=shop["cashier"]).status_code == 403


def test_staff_change_own_pin(client, shop):
    h = shop["waiter"]
    assert client.post("/api/auth/change-pin", headers=h,
                       json={"current_password": "wrong", "new_pin": "4545"}).status_code == 400
    assert client.post("/api/auth/change-pin", headers=h,
                       json={"current_password": "pass123", "new_pin": "1202"}).status_code == 409
    assert client.post("/api/auth/change-pin", headers=h,
                       json={"current_password": "pass123", "new_pin": "4545"}).status_code == 200
    r = client.post("/api/auth/pin-login", json={"pin": "4545", "restaurant_code": shop["code"]})
    assert r.status_code == 200 and r.json()["user"]["role"] == "waiter"


def test_cash_drawer_shift(client, shop):
    cashier = shop["cashier"]
    assert client.post("/api/shifts/open", headers=shop["waiter"],
                       json={"opening_float": 1000}).status_code == 403
    r = client.post("/api/shifts/open", headers=cashier, json={"opening_float": 1000})
    assert r.status_code == 201, r.text
    assert client.post("/api/shifts/open", headers=cashier, json={}).status_code == 409
    bill = _checkout(client, shop, _order(client, shop)["id"]).json()
    client.post("/api/shifts/current/movement", headers=cashier,
                json={"kind": "out", "amount": 200, "reason": "Vegetables"})
    cur = client.get("/api/shifts/current", headers=cashier).json()["shift"]
    assert cur["cash_sales"] == bill["grand_total"]
    expected = round(1000 + bill["grand_total"] - 200, 2)
    assert cur["expected_cash"] == expected
    r = client.post("/api/shifts/current/close", headers=cashier, json={"counted_cash": expected - 50})
    assert r.status_code == 200
    assert r.json()["difference"] == -50 and r.json()["status"] == "closed"
    assert client.get("/api/shifts/current", headers=cashier).json()["shift"] is None
    log = client.get("/api/activity?category=cash", headers=shop["admin"]).json()["entries"]
    assert any("short Rs 50.00" in e["text"] for e in log)


def test_staff_report(client, shop):
    r = client.get("/api/reports/staff", headers=shop["admin"])
    assert r.status_code == 200
    rows = {s["name"]: s for s in r.json()["staff"]}
    assert rows["Waiter One"]["orders"] >= 1 and rows["Waiter One"]["sales"] > 0
    assert rows["Cashier One"]["bills_settled"] >= 1
    assert rows["Kitchen One"]["tickets_accepted"] >= 1
    assert client.get("/api/reports/staff", headers=shop["kitchen"]).status_code == 403
