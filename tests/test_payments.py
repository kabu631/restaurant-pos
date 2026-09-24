"""Paying: one-step checkout, split tenders, receipts, voids and daily totals."""


def preview(client, headers, order_id, **kw):
    return client.post("/api/billing/preview", headers=headers, json={"order_id": order_id, **kw}).json()


def checkout(client, headers, order_id, payments, **kw):
    return client.post("/api/billing/checkout", headers=headers,
                       json={"order_id": order_id, "payments": payments, **kw})


def test_cash_payment_with_change_closes_order_and_frees_table(client, cashier, open_order):
    order = open_order(items=[("Chicken Momo", 2)], send_kot=True)      # 500 → 621.50
    total = preview(client, cashier, order["id"])["grand_total"]
    assert total == 621.5
    r = checkout(client, cashier, order["id"], [{"method": "cash", "tendered": 1000}])
    assert r.status_code == 200, r.text
    bill = r.json()
    assert bill["payment_status"] == "paid" and bill["payment_method"] == "cash"
    assert bill["change"] == 378.5
    assert client.get(f"/api/orders/{order['id']}", headers=cashier).json()["status"] == "completed"
    tables = client.get("/api/tables/overview", headers=cashier).json()["tables"]
    assert next(t for t in tables if t["id"] == order["table_id"])["status"] == "free"


def test_split_payment_card_plus_cash(client, cashier, open_order):
    order = open_order(items=[("Dal Bhat Set Veg", 2)])
    total = preview(client, cashier, order["id"])["grand_total"]
    bill = checkout(client, cashier, order["id"], [
        {"method": "card", "amount": 500, "reference": "AUTH123"},
        {"method": "cash", "amount": round(total - 500, 2)},
    ]).json()
    assert bill["payment_method"] == "split"
    assert [(p["method"], p["amount"]) for p in bill["payments"]] == [("card", 500.0), ("cash", round(total - 500, 2))]


def test_payments_must_add_up(client, cashier, open_order):
    order = open_order()
    r = checkout(client, cashier, order["id"], [{"method": "cash", "amount": 1}])
    assert r.status_code == 400 and "add up" in r.json()["detail"]


def test_short_cash_is_rejected(client, cashier, open_order):
    order = open_order()
    r = checkout(client, cashier, order["id"], [{"method": "cash", "tendered": 10}])
    assert r.status_code == 400


def test_wallets_can_be_confirmed_by_the_cashier(client, cashier, open_order):
    """A static eSewa/Khalti QR at the counter: the cashier checks their phone and confirms."""
    order = open_order()
    bill = checkout(client, cashier, order["id"], [{"method": "esewa", "reference": "ES-99"}]).json()
    assert bill["payments"][0]["reference"] == "ES-99"


def test_waiters_cannot_take_payment(client, waiter, open_order):
    order = open_order()
    assert checkout(client, waiter, order["id"], [{"method": "cash"}]).status_code == 403


def test_checkout_sends_forgotten_items_to_the_kitchen(client, cashier, kitchen, open_order):
    order = open_order(items=[("Thukpa", 1)])                           # never sent
    bill = checkout(client, cashier, order["id"], [{"method": "cash"}]).json()
    assert bill["kot"]["items_sent"] == 1
    tickets = client.get("/api/kitchen/tickets", headers=kitchen).json()
    assert any(t["order_id"] == order["id"] for t in tickets)


def test_discount_and_service_charge_toggle(client, cashier, open_order):
    order = open_order(items=[("Chicken Momo", 4)])                     # 1000
    p = preview(client, cashier, order["id"], discount_type="percentage", discount_value=10,
                include_service_charge=False)
    assert p["discount_amount"] == 100 and p["service_charge"] == 0
    bill = checkout(client, cashier, order["id"], [{"method": "card"}], discount_type="percentage",
                    discount_value=10, include_service_charge=False, customer_pan="123456789").json()
    assert bill["grand_total"] == p["grand_total"] == 1017.0
    assert bill["customer_pan"] == "123456789"


def test_bill_numbers_are_sequential(client, cashier, open_order):
    numbers = []
    for _ in range(2):
        order = open_order()
        numbers.append(checkout(client, cashier, order["id"], [{"method": "cash"}]).json()["bill_number"])
    first, second = (int(n.rsplit("-", 1)[1]) for n in numbers)
    assert second == first + 1


def test_bill_numbers_are_per_restaurant(client, other_restaurant):
    h = other_restaurant["headers"]
    cat = client.post("/api/menu/categories", headers=h, json={"name": "Food"}).json()
    item = client.post("/api/menu/items", headers=h,
                       json={"category_id": cat["id"], "name": "Sel Roti", "price": 50}).json()
    order = client.post("/api/orders", headers=h, json={
        "order_type": "takeaway", "items": [{"menu_item_id": item["id"], "quantity": 2}]}).json()
    bill = checkout(client, h, order["id"], [{"method": "cash"}]).json()
    assert bill["bill_number"].endswith("-000001")      # its own sequence, not shared


def test_receipt_page_and_copy_of_original(client, cashier, open_order):
    order = open_order()
    bill = checkout(client, cashier, order["id"], [{"method": "cash"}]).json()
    page = client.get(f"/receipt/{bill['id']}", headers=cashier)
    assert page.status_code == 200 and bill["bill_number"] in page.text
    assert "COPY OF ORIGINAL - 1" not in page.text
    client.patch(f"/api/billing/bills/{bill['id']}/print", headers=cashier)
    client.patch(f"/api/billing/bills/{bill['id']}/print", headers=cashier)
    assert "COPY OF ORIGINAL - 1" in client.get(f"/receipt/{bill['id']}", headers=cashier).text


def test_void_paid_bill_is_admin_only_and_needs_reason(client, cashier, admin, open_order):
    order = open_order()
    bill = checkout(client, cashier, order["id"], [{"method": "cash"}]).json()
    url = f"/api/billing/bills/{bill['id']}/void"
    assert client.post(url, headers=cashier, json={"reason": "x"}).status_code == 403
    assert client.post(url, headers=admin, json={"reason": " "}).status_code == 400
    voided = client.post(url, headers=admin, json={"reason": "Refund to customer"}).json()
    assert voided["payment_status"] == "void"
    assert client.get(f"/api/orders/{order['id']}", headers=admin).json()["status"] == "cancelled"


def test_voided_unpaid_bill_keeps_order_open_for_a_new_bill(client, cashier, admin, open_order):
    order = open_order()
    first = client.post("/api/billing/bills", headers=cashier, json={"order_id": order["id"]}).json()
    client.post(f"/api/billing/bills/{first['id']}/void", headers=admin, json={"reason": "Wrong discount"})
    assert client.get(f"/api/orders/{order['id']}", headers=admin).json()["status"] == "active"
    second = checkout(client, cashier, order["id"], [{"method": "cash"}]).json()
    assert second["bill_number"] != first["bill_number"] and second["payment_status"] == "paid"


def test_adding_items_updates_an_issued_unpaid_bill(client, cashier, menu, open_order):
    order = open_order()
    bill = client.post("/api/billing/bills", headers=cashier, json={"order_id": order["id"]}).json()
    client.post(f"/api/orders/{order['id']}/items", headers=cashier,
                json={"menu_item_id": menu["Kheer"]["id"], "quantity": 1})
    updated = client.get(f"/api/billing/bills/{bill['id']}", headers=cashier).json()
    assert updated["subtotal"] == bill["subtotal"] + 120


def test_today_summary_splits_takings_by_method(client, cashier, open_order):
    before = client.get("/api/billing/summary/today", headers=cashier).json()
    order = open_order()
    total = preview(client, cashier, order["id"])["grand_total"]
    checkout(client, cashier, order["id"], [{"method": "khalti", "amount": 100},
                                            {"method": "cash", "amount": round(total - 100, 2)}])
    after = client.get("/api/billing/summary/today", headers=cashier).json()
    assert after["bill_count"] == before["bill_count"] + 1
    assert after["by_payment_method"]["khalti"] == round(before["by_payment_method"].get("khalti", 0) + 100, 2)


def test_payment_method_can_be_turned_off(client, admin, cashier, open_order):
    client.put("/api/settings/bulk", headers=admin, json={"settings": {"payment_methods": "cash,card"}})
    try:
        methods = client.get("/api/billing/payment-methods", headers=cashier).json()["methods"]
        assert [m["key"] for m in methods] == ["cash", "card"]
        order = open_order()
        assert checkout(client, cashier, order["id"], [{"method": "esewa"}]).status_code == 400
    finally:
        client.put("/api/settings/bulk", headers=admin,
                   json={"settings": {"payment_methods": "cash,card,qr,esewa,khalti"}})


def test_vat_can_be_switched_off_for_pan_only_restaurants(client, admin, cashier, open_order):
    client.put("/api/settings/bulk", headers=admin, json={"settings": {"vat_enabled": "false"}})
    try:
        order = open_order(items=[("Chicken Momo", 4)])                 # 1000 + 10% SC
        assert preview(client, cashier, order["id"])["grand_total"] == 1100.0
    finally:
        client.put("/api/settings/bulk", headers=admin, json={"settings": {"vat_enabled": "true"}})


def test_merchant_qr_upload_is_validated(client, admin):
    bad = client.put("/api/settings/payment-qr/esewa", headers=admin, json={"image": "data:text/html;base64,PGI+"})
    assert bad.status_code == 400
    png = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
           "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    ok = client.put("/api/settings/payment-qr/esewa", headers=admin, json={"image": png})
    assert ok.status_code == 200
    methods = client.get("/api/billing/payment-methods", headers=admin).json()["methods"]
    assert next(m for m in methods if m["key"] == "esewa")["qr_image"] == png
    client.put("/api/settings/payment-qr/esewa", headers=admin, json={"image": None})


def test_create_bill_first_then_take_payment_with_the_same_number(client, cashier, kitchen, menu, open_order):
    """Table → food → kitchen → create bill (printed for the guest) → payment later."""
    order = open_order(items=[("Chicken Momo", 2)], send_kot=True)
    client.post(f"/api/orders/{order['id']}/items", headers=cashier,          # a late extra, not sent
                json={"menu_item_id": menu["Kheer"]["id"], "quantity": 1})
    bill = client.post("/api/billing/bills", headers=cashier, json={"order_id": order["id"]}).json()
    assert bill["payment_status"] == "unpaid"
    assert bill["kot"]["items_sent"] == 1                                     # billed food always gets made
    assert any(t["order_id"] == order["id"] and t["kot_number"] == bill["kot"]["kot_number"]
               for t in client.get("/api/kitchen/tickets", headers=kitchen).json())

    p = preview(client, cashier, order["id"])
    assert p["bill"]["bill_number"] == bill["bill_number"] and p["pending_items"] == 0
    card = next(t for t in client.get("/api/tables/overview", headers=cashier).json()["tables"]
                if t["id"] == order["table_id"])
    assert card["order"]["bill_open"] is True

    paid = checkout(client, cashier, order["id"], [{"method": "cash", "tendered": 2000}]).json()
    assert paid["bill_number"] == bill["bill_number"] and paid["payment_status"] == "paid"
    assert paid["grand_total"] == bill["grand_total"]


def test_created_bill_can_be_updated_before_payment(client, cashier, open_order):
    order = open_order(items=[("Chicken Momo", 4)])                          # 1000
    bill = client.post("/api/billing/bills", headers=cashier, json={"order_id": order["id"]}).json()
    assert bill["grand_total"] == 1243.0
    updated = client.patch(f"/api/billing/bills/{bill['id']}/update", headers=cashier, json={
        "include_service_charge": False, "discount_type": "flat", "discount_value": 100,
        "customer_name": "ABC Traders", "customer_pan": "600123456"}).json()
    assert updated["bill_number"] == bill["bill_number"]
    assert updated["grand_total"] == round(900 * 1.13, 2)
    assert updated["customer_pan"] == "600123456"
