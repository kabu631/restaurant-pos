"""Permissions, tenant isolation, login protection and page rendering."""
import uuid

import pytest


def test_restaurants_cannot_see_each_others_orders_or_bills(client, cashier, other_restaurant, open_order):
    order = open_order()
    bill = client.post("/api/billing/checkout", headers=cashier,
                       json={"order_id": order["id"], "payments": [{"method": "cash"}]}).json()
    h = other_restaurant["headers"]
    assert client.get(f"/api/orders/{order['id']}", headers=h).status_code == 404
    assert client.get(f"/api/billing/bills/{bill['id']}", headers=h).status_code == 404
    assert client.post(f"/api/billing/bills/{bill['id']}/fonepay-qr", headers=h).status_code == 404
    assert client.get(f"/receipt/{bill['id']}", headers=h).status_code == 404


def test_recipe_rows_are_tenant_scoped(client, admin, menu, other_restaurant):
    ing = client.post("/api/inventory/ingredients", headers=admin,
                      json={"name": f"Flour {uuid.uuid4().hex[:4]}", "unit": "kg", "cost_per_unit": 80}).json()
    row = client.post(f"/api/inventory/recipes/{menu['Veg Momo']['id']}", headers=admin,
                      json={"ingredient_id": ing["id"], "quantity_used": 0.1, "unit": "kg"}).json()
    h = other_restaurant["headers"]
    assert client.put(f"/api/inventory/recipes/items/{row['id']}", headers=h,
                      json={"quantity_used": 9}).status_code == 404
    assert client.delete(f"/api/inventory/recipes/items/{row['id']}", headers=h).status_code == 404


def test_reports_are_for_managers_only(client, waiter, kitchen, cashier, admin):
    for h in (waiter, kitchen):
        assert client.get("/api/reports/revenue?period=daily", headers=h).status_code == 403
        assert client.get("/api/reports/export/sales", headers=h).status_code == 403
    assert client.get("/api/reports/revenue?period=daily", headers=cashier).status_code == 200
    assert client.get("/api/reports/export/audit", headers=cashier).status_code == 403
    assert client.get("/api/reports/export/audit", headers=admin).status_code == 200


def test_revenue_report_counts_todays_sales(client, cashier, open_order):
    before = client.get("/api/reports/revenue?period=daily", headers=cashier).json()
    order = open_order()
    bill = client.post("/api/billing/checkout", headers=cashier,
                       json={"order_id": order["id"], "payments": [{"method": "card"}]}).json()
    after = client.get("/api/reports/revenue?period=daily", headers=cashier).json()
    assert after["total_orders"] == before["total_orders"] + 1
    assert round(after["total_revenue"] - before["total_revenue"], 2) == bill["grand_total"]
    for period in ("weekly", "monthly", "yearly"):
        assert client.get(f"/api/reports/revenue?period={period}", headers=cashier).status_code == 200


def test_pins_must_be_unique_within_a_restaurant(client, admin):
    r = client.post("/api/users", headers=admin, json={
        "full_name": "Dup", "username": f"dup{uuid.uuid4().hex[:5]}", "password": "secret1",
        "role": "waiter", "pin": "2222"})                       # waiter1 already uses 2222
    assert r.status_code == 409


def test_pin_login_lands_on_the_role_home_page(client):
    r = client.post("/api/auth/pin-login", json={"pin": "3333", "restaurant_code": "demo"})
    assert r.status_code == 200
    assert r.json()["user"]["home"] == "/kitchen"
    assert "access_token" in r.cookies


def test_repeated_wrong_passwords_lock_the_login(client):
    name = f"ghost{uuid.uuid4().hex[:5]}"
    codes = [client.post("/api/auth/login", json={"username": name, "password": "nope",
                                                  "restaurant_code": "demo"}).status_code
             for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_superadmin_cannot_open_pos_orders(client):
    r = client.post("/api/auth/login", json={"username": "superadmin", "password": "superadmin123"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.post("/api/orders", headers=h, json={"order_type": "takeaway"}).status_code == 400


@pytest.mark.parametrize("path", ["/login", "/dashboard", "/tables", "/orders", "/kitchen", "/billing",
                                  "/reservations", "/menu", "/inventory", "/users", "/reports",
                                  "/settings", "/register", "/admin"])
def test_pages_render(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "cdn.tailwindcss.com" not in r.text            # works without internet


def test_print_pages_need_login(client, open_order, waiter):
    order = open_order(send_kot=True)
    anon = client.__class__(client.app)                   # a fresh client without the login cookie
    assert anon.get(f"/check/{order['id']}").status_code == 401
    assert client.get(f"/check/{order['id']}", headers=waiter).status_code == 200
    kot = order["kot"]["kot_number"]
    page = client.get(f"/kot-print/{order['id']}/{kot}", headers=waiter)
    assert page.status_code == 200 and f"KOT #{kot}" in page.text


def test_pos_settings_are_readable_by_any_staff(client, waiter):
    s = client.get("/api/settings/pos", headers=waiter).json()
    assert "No spice" in s["quick_notes"] and s["tax"]["vat_rate"] == 13


def test_static_assets_are_served(client):
    for path in ("/static/js/pos.js", "/static/js/payment.js", "/static/vendor/tailwindcss-3.4.17.js"):
        assert client.get(path).status_code == 200
