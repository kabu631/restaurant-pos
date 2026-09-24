"""Taking orders and connecting them to the kitchen (KOT)."""


def kitchen_ticket(client, headers, order_id):
    return [t for t in client.get("/api/kitchen/tickets", headers=headers).json()
            if t["order_id"] == order_id]


def test_create_order_with_items_and_kot_in_one_call(client, waiter, open_order):
    order = open_order(items=[("Chicken Momo", 2), ("Veg Momo", 1)], send_kot=True)
    assert order["kot"]["kot_number"] >= 1
    assert order["kot"]["items_sent"] == 2
    assert order["counts"]["in_kitchen"] == 2
    tickets = kitchen_ticket(client, waiter, order["id"])
    assert len(tickets) == 1 and len(tickets[0]["items"]) == 2


def test_kot_numbers_run_daily_across_orders(open_order):
    first = open_order(send_kot=True)["kot"]["kot_number"]
    second = open_order(send_kot=True)["kot"]["kot_number"]
    assert second == first + 1          # not "KOT #1" on every order any more


def test_table_is_occupied_and_second_order_points_to_the_first(client, waiter, menu, new_table):
    table = new_table()
    r = client.post("/api/orders", headers=waiter, json={"table_id": table["id"]})
    assert r.status_code == 201
    first_id = r.json()["id"]
    r = client.post("/api/orders", headers=waiter, json={"table_id": table["id"]})
    assert r.status_code == 409
    assert r.headers["X-Order-Id"] == str(first_id)


def test_same_dish_with_different_notes_stays_separate(client, waiter, menu, open_order):
    order = open_order(items=[])
    momo = menu["Chicken Momo"]["id"]
    body = {"items": [
        {"menu_item_id": momo, "quantity": 1},
        {"menu_item_id": momo, "quantity": 1, "notes": "no spice"},
        {"menu_item_id": momo, "quantity": 2},
    ]}
    detail = client.post(f"/api/orders/{order['id']}/items/bulk", headers=waiter, json=body).json()
    lines = {(i["notes"], i["quantity"]) for i in detail["items"]}
    assert lines == {(None, 3), ("no spice", 1)}


def test_bulk_add_and_send_fires_saved_items_too(client, waiter, menu, open_order):
    order = open_order(items=[("Veg Momo", 1)])            # saved, not sent
    detail = client.post(f"/api/orders/{order['id']}/items/bulk", headers=waiter, json={
        "items": [{"menu_item_id": menu["Thukpa"]["id"], "quantity": 1}], "send_kot": True,
    }).json()
    assert detail["kot"]["items_sent"] == 2
    assert detail["counts"]["pending"] == 0


def test_bottled_drinks_skip_the_kitchen(client, waiter, open_order):
    order = open_order(items=[("Coke", 2), ("Chicken Momo", 1)], send_kot=True)
    assert order["kot"]["items_direct"] == 1
    coke = next(i for i in order["items"] if i["name"] == "Coke")
    assert coke["kot_status"] == "served"
    ticket = kitchen_ticket(client, waiter, order["id"])[0]
    assert [i["name"] for i in ticket["items"]] == ["Chicken Momo"]


def test_bar_items_are_tagged_for_the_bar_station(client, waiter, open_order):
    order = open_order(items=[("Milk Tea", 2), ("Chicken Momo", 1)], send_kot=True)
    assert order["kot"]["stations"] == ["bar", "kitchen"]
    bar = client.get("/api/kitchen/tickets?station=bar", headers=waiter).json()
    mine = [t for t in bar if t["order_id"] == order["id"]]
    assert [i["name"] for i in mine[0]["items"]] == ["Milk Tea"]


def test_food_in_the_kitchen_cannot_be_changed_or_removed(client, admin, waiter, open_order):
    order = open_order(send_kot=True)
    item = order["items"][0]
    for h in (waiter, admin):                  # not even an admin
        r = client.put(f"/api/orders/{order['id']}/items/{item['id']}", headers=h, json={"quantity": 5})
        assert r.status_code == 400 and "can't be cancelled" in r.json()["detail"]
        r = client.delete(f"/api/orders/{order['id']}/items/{item['id']}", headers=h)
        assert r.status_code == 400
    # No "un-sending" a dish so it could be deleted
    r = client.patch(f"/api/orders/{order['id']}/items/{item['id']}/kot-status", headers=admin,
                     json={"kot_status": "pending"})
    assert r.status_code == 400
    # There is no void for kitchen items any more
    r = client.post(f"/api/orders/{order['id']}/items/{item['id']}/void", headers=admin, json={"reason": "x"})
    assert r.status_code in (404, 405)


def test_order_with_food_in_the_kitchen_cannot_be_cancelled(client, waiter, cashier, admin, open_order):
    order = open_order(send_kot=True)
    for h in (waiter, cashier, admin):
        r = client.post(f"/api/orders/{order['id']}/cancel", headers=h, json={"reason": "Customer left"})
        assert r.status_code == 409 and "can't be cancelled" in r.json()["detail"]
        r = client.patch(f"/api/orders/{order['id']}/status", headers=h, json={"status": "cancelled"})
        assert r.status_code == 409
    # Nor can it be closed without paying
    r = client.patch(f"/api/orders/{order['id']}/status", headers=admin, json={"status": "completed"})
    assert r.status_code == 400
    assert len(kitchen_ticket(client, waiter, order["id"])) == 1       # still cooking


def test_bottled_drinks_served_directly_also_lock_the_order(client, cashier, open_order):
    order = open_order(items=[("Coke", 1)], send_kot=True)            # never reaches the kitchen
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=cashier, json={}).status_code == 409


def test_unsent_items_can_still_be_removed_and_the_order_cancelled(client, waiter, open_order):
    order = open_order(items=[("Chicken Momo", 2), ("Veg Momo", 1)])  # saved, not sent
    item = order["items"][0]
    r = client.put(f"/api/orders/{order['id']}/items/{item['id']}", headers=waiter, json={"quantity": 1})
    assert r.status_code == 200
    assert client.delete(f"/api/orders/{order['id']}/items/{item['id']}", headers=waiter).status_code == 204
    assert client.post(f"/api/orders/{order['id']}/cancel", headers=waiter, json={}).status_code == 200
    tables = client.get("/api/tables/overview", headers=waiter).json()["tables"]
    assert next(t for t in tables if t["id"] == order["table_id"])["status"] == "free"


def test_move_order_to_another_table(client, waiter, open_order, new_table):
    order = open_order()
    target = new_table()
    moved = client.post(f"/api/orders/{order['id']}/transfer", headers=waiter,
                        json={"table_id": target["id"]}).json()
    assert moved["table_id"] == target["id"]
    tables = {t["id"]: t for t in client.get("/api/tables/overview", headers=waiter).json()["tables"]}
    assert tables[order["table_id"]]["status"] == "free"
    assert tables[target["id"]]["status"] == "occupied"


def test_kitchen_flow_start_ready_served(client, kitchen, waiter, open_order):
    order = open_order(items=[("Chicken Momo", 1), ("Veg Momo", 2)], send_kot=True)
    kot = order["kot"]["kot_number"]
    url = f"/api/kitchen/tickets/{order['id']}/{kot}/advance"
    assert client.patch(url, headers=kitchen).json()["kot_status"] == "preparing"
    assert client.patch(url, headers=kitchen).json()["kot_status"] == "ready"

    ready = client.get("/api/kitchen/ready", headers=waiter).json()
    assert any(o["order_id"] == order["id"] for o in ready["orders"])
    overview = client.get("/api/tables/overview", headers=waiter).json()
    card = next(t for t in overview["tables"] if t["id"] == order["table_id"])
    assert card["order"]["ready"] == 3

    served = client.post(f"/api/orders/{order['id']}/serve-ready", headers=waiter).json()
    assert served["served"] == 2
    assert kitchen_ticket(client, waiter, order["id"]) == []


def test_bump_and_undo_single_item(client, kitchen, open_order):
    order = open_order(send_kot=True)
    item_id = order["items"][0]["id"]
    r = client.patch(f"/api/kitchen/items/{item_id}/bump", headers=kitchen).json()
    assert (r["previous"], r["kot_status"]) == ("sent", "preparing")
    r = client.patch(f"/api/kitchen/items/{item_id}/status", headers=kitchen, json={"kot_status": "sent"})
    assert r.json()["kot_status"] == "sent"


def test_kitchen_age_is_computed_by_the_server(client, kitchen, open_order):
    order = open_order(send_kot=True)
    ticket = kitchen_ticket(client, kitchen, order["id"])[0]
    assert 0 <= ticket["age_sec"] < 60
    assert ticket["sent_at"].endswith("+05:45")


def test_table_goes_to_the_cashier_once_the_kitchen_accepts(client, waiter, kitchen, cashier, open_order):
    order = open_order(items=[("Chicken Momo", 2), ("Veg Momo", 1)], send_kot=True)

    def card():
        tables = client.get("/api/tables/overview", headers=cashier).json()["tables"]
        return next(t for t in tables if t["id"] == order["table_id"])["order"]

    assert card()["ready_to_bill"] is False and card()["awaiting_accept"] == 3
    p = client.post("/api/billing/preview", headers=cashier, json={"order_id": order["id"]}).json()
    assert p["awaiting_accept"] == 2                                    # two lines on the ticket

    kot = order["kot"]["kot_number"]
    r = client.patch(f"/api/kitchen/tickets/{order['id']}/{kot}/advance", headers=kitchen).json()
    assert r["kot_status"] == "preparing"                               # "✓ Accept order"
    assert card()["ready_to_bill"] is True and card()["awaiting_accept"] == 0


def test_drinks_served_directly_are_ready_to_bill_straight_away(client, cashier, open_order):
    order = open_order(items=[("Coke", 2)], send_kot=True)
    tables = client.get("/api/tables/overview", headers=cashier).json()["tables"]
    assert next(t for t in tables if t["id"] == order["table_id"])["order"]["ready_to_bill"] is True


def test_cashier_lands_on_billing(client):
    r = client.post("/api/auth/pin-login", json={"pin": "1111", "restaurant_code": "demo"})
    assert r.json()["user"]["home"] == "/billing"
