import asyncio
import httpx
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.main import app


async def run():
    passed = 0
    failed = 0

    def ok(label, val):
        nonlocal passed
        print(f"  PASS  {label}: {val}")
        passed += 1

    def fail(label, val):
        nonlocal failed
        print(f"  FAIL  {label}: {val}")
        failed += 1

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:

        # 1. Root redirect
        r = await c.get("/", follow_redirects=False)
        (ok if r.status_code in (307, 302) else fail)("GET / redirects to /login", r.status_code)

        # 2. Login page
        r = await c.get("/login")
        (ok if r.status_code == 200 else fail)("GET /login returns 200", r.status_code)
        (ok if "pin-login" in r.text else fail)("Login page has PIN form", "found" if "pin-login" in r.text else "MISSING")

        # 3. Bad credentials
        r = await c.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        (ok if r.status_code == 401 else fail)("POST /api/auth/login bad creds = 401", r.status_code)

        # 4. Good login
        r = await c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        (ok if r.status_code == 200 else fail)("POST /api/auth/login good = 200", r.status_code)
        if r.status_code != 200:
            print("    ERROR:", r.text[:200])
            fail("Cannot continue without token", "")
            return
        data = r.json()
        token = data["access_token"]
        uname = data["user"]["username"]
        role = data["user"]["role"]
        ok("Login returns token + user", f"{uname} / {role}")

        headers = {"Authorization": f"Bearer {token}"}

        # 5. /me
        r = await c.get("/api/auth/me", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/auth/me = 200", r.status_code)
        me = r.json()
        ok("/me returns correct user", me.get("username"))

        # 6. PIN login
        r = await c.post("/api/auth/pin-login", json={"pin": "0000"})
        (ok if r.status_code == 200 else fail)("POST /api/auth/pin-login = 200", r.status_code)

        # 7. Bad PIN
        r = await c.post("/api/auth/pin-login", json={"pin": "9999"})
        (ok if r.status_code == 401 else fail)("POST /api/auth/pin-login bad pin = 401", r.status_code)

        # 8. List categories
        r = await c.get("/api/menu/categories", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/menu/categories = 200", r.status_code)
        ok("Categories list is array", f"{len(r.json())} items")

        # 9. Create category
        r = await c.post("/api/menu/categories", json={"name": "Test Cat", "display_order": 99}, headers=headers)
        (ok if r.status_code == 201 else fail)("POST /api/menu/categories = 201", r.status_code)
        cat_id = r.json()["id"]
        ok("Category created with id", cat_id)

        # 10. Update category
        r = await c.put(f"/api/menu/categories/{cat_id}", json={"name": "Test Cat Updated"}, headers=headers)
        (ok if r.status_code == 200 else fail)("PUT /api/menu/categories/{id} = 200", r.status_code)
        ok("Category name updated", r.json()["name"])

        # 11. Create menu item
        r = await c.post("/api/menu/items",
                         json={"category_id": cat_id, "name": "Test Momo", "price": 250, "is_vat_applicable": True},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("POST /api/menu/items = 201", r.status_code)
        if r.status_code != 201:
            print("    ERROR:", r.text[:200])
        item_id = r.json()["id"]
        ok("Item created with id", item_id)

        # 12. Update item
        r = await c.put(f"/api/menu/items/{item_id}", json={"price": 280}, headers=headers)
        (ok if r.status_code == 200 else fail)("PUT /api/menu/items/{id} = 200", r.status_code)
        ok("Item price updated", r.json()["price"])

        # 13. Toggle availability
        orig_avail = r.json()["is_available"]
        r = await c.patch(f"/api/menu/items/{item_id}/toggle", headers=headers)
        (ok if r.status_code == 200 else fail)("PATCH /items/{id}/toggle = 200", r.status_code)
        new_avail = r.json()["is_available"]
        (ok if new_avail != orig_avail else fail)("Toggle flips availability", f"{orig_avail} -> {new_avail}")

        # 14. Profit endpoint
        r = await c.get(f"/api/menu/items/{item_id}/profit", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /items/{id}/profit = 200", r.status_code)
        p = r.json()
        ok("Profit response has margin", f"{p['margin_percent']}%")

        # 15. Filter items by category
        r = await c.get(f"/api/menu/items?category_id={cat_id}", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/menu/items?category_id= = 200", r.status_code)
        ok("Filtered items count", len(r.json()))

        # 16. Menu page HTML
        r = await c.get("/menu")
        (ok if r.status_code == 200 else fail)("GET /menu page = 200", r.status_code)
        (ok if "items-container" in r.text else fail)("Menu page has items-container div", "found" if "items-container" in r.text else "MISSING")

        # 17. Unauthorized access without token
        r = await c.post("/api/menu/categories", json={"name": "No Auth"})
        (ok if r.status_code == 401 else fail)("POST categories without token = 401", r.status_code)

        # 18. List tables (empty at start)
        r = await c.get("/api/tables")
        (ok if r.status_code == 200 else fail)("GET /api/tables = 200", r.status_code)
        ok("Tables list is array", f"{len(r.json())} items")

        # 19. Create table
        r = await c.post("/api/tables",
                         json={"table_number": "T1", "capacity": 4, "floor": "Ground"},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("POST /api/tables = 201", r.status_code)
        tbl_id = r.json()["id"]
        ok("Table created with id", tbl_id)

        # 20. Duplicate table number rejected
        r = await c.post("/api/tables",
                         json={"table_number": "T1", "capacity": 2, "floor": "Ground"},
                         headers=headers)
        (ok if r.status_code == 409 else fail)("Duplicate table_number = 409", r.status_code)

        # 21. Update table
        r = await c.put(f"/api/tables/{tbl_id}",
                        json={"capacity": 6},
                        headers=headers)
        (ok if r.status_code == 200 else fail)("PUT /api/tables/{id} = 200", r.status_code)
        ok("Table capacity updated", r.json()["capacity"])

        # 22. Change status
        r = await c.patch(f"/api/tables/{tbl_id}/status",
                          json={"status": "occupied"},
                          headers=headers)
        (ok if r.status_code == 200 else fail)("PATCH /api/tables/{id}/status = 200", r.status_code)
        (ok if r.json()["status"] == "occupied" else fail)("Status changed to occupied", r.json()["status"])

        # 23. Invalid status rejected
        r = await c.patch(f"/api/tables/{tbl_id}/status",
                          json={"status": "broken"},
                          headers=headers)
        (ok if r.status_code == 400 else fail)("Invalid status = 400", r.status_code)

        # 24. Tables by floor
        r = await c.get("/api/tables/floor/Ground")
        (ok if r.status_code == 200 else fail)("GET /api/tables/floor/Ground = 200", r.status_code)
        ok("Ground floor tables", len(r.json()))

        # 25. Tables page HTML
        r = await c.get("/tables")
        (ok if r.status_code == 200 else fail)("GET /tables page = 200", r.status_code)
        (ok if "floor-plan" in r.text else fail)("Tables page has floor-plan div", "found" if "floor-plan" in r.text else "MISSING")

        # 26. Delete table
        r = await c.delete(f"/api/tables/{tbl_id}", headers=headers)
        (ok if r.status_code == 204 else fail)("DELETE /api/tables/{id} = 204", r.status_code)

        # --- Orders ---
        # 27. Create a table + fresh available item for order tests
        # Clean up T10 if it already exists from a prior run
        r_all = await c.get("/api/tables")
        for _t in r_all.json():
            if _t["table_number"] == "T10":
                await c.delete(f"/api/tables/{_t['id']}", headers=headers)

        r = await c.post("/api/tables",
                         json={"table_number": "T10", "capacity": 4, "floor": "Ground"},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("Create T10 for order tests = 201", r.status_code)
        order_tbl_id = r.json()["id"]

        r = await c.post("/api/menu/items",
                         json={"category_id": cat_id, "name": "Order Test Item",
                               "price": 150, "is_vat_applicable": False, "is_available": True},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("Create available item for order tests = 201", r.status_code)
        avail_item_id = r.json()["id"]

        # 28. Create dine-in order
        r = await c.post("/api/orders",
                         json={"order_type": "dine_in", "table_id": order_tbl_id},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("POST /api/orders = 201", r.status_code)
        order_id = r.json()["id"]
        ok("Order created", f"id={order_id}")

        # 29. Table status auto-set to occupied
        r = await c.get(f"/api/tables")
        tbl_data = next((t for t in r.json() if t["id"] == order_tbl_id), None)
        (ok if tbl_data and tbl_data["status"] == "occupied" else fail)(
            "Table auto-set to occupied on order create", tbl_data["status"] if tbl_data else "missing")

        # 30. Add item to order
        r = await c.post(f"/api/orders/{order_id}/items",
                         json={"menu_item_id": avail_item_id, "quantity": 2},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("POST /api/orders/{id}/items = 201", r.status_code)
        oi_id = r.json()["id"]
        ok("Order item added", f"qty={r.json()['quantity']}")

        # 31. Add same item merges quantity
        r = await c.post(f"/api/orders/{order_id}/items",
                         json={"menu_item_id": avail_item_id, "quantity": 1},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("Adding same item merges = 201", r.status_code)
        (ok if r.json()["quantity"] == 3 else fail)("Merged qty = 3", r.json()["quantity"])

        # 32. Get order detail
        r = await c.get(f"/api/orders/{order_id}", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/orders/{id} = 200", r.status_code)
        ok("Order subtotal", r.json()["subtotal"])

        # 33. Send KOT
        r = await c.post(f"/api/orders/{order_id}/kot", headers=headers)
        (ok if r.status_code == 200 else fail)("POST /api/orders/{id}/kot = 200", r.status_code)
        ok("KOT sent", f"kot#{r.json()['kot_number']} — {r.json()['items_sent']} item(s)")

        # 34. No pending items = 400
        r = await c.post(f"/api/orders/{order_id}/kot", headers=headers)
        (ok if r.status_code == 400 else fail)("KOT with no pending items = 400", r.status_code)

        # 35. List orders
        r = await c.get("/api/orders", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/orders = 200", r.status_code)
        ok("Orders list count", len(r.json()))

        # 36. Filter by status
        r = await c.get("/api/orders?status_filter=active", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/orders?status_filter=active = 200", r.status_code)
        ok("Active orders", len(r.json()))

        # 37. Update order status to completed
        r = await c.patch(f"/api/orders/{order_id}/status",
                          json={"status": "completed"}, headers=headers)
        (ok if r.status_code == 200 else fail)("PATCH order status completed = 200", r.status_code)

        # 38. Table freed on order complete
        r = await c.get("/api/tables")
        tbl_data = next((t for t in r.json() if t["id"] == order_tbl_id), None)
        (ok if tbl_data and tbl_data["status"] == "free" else fail)(
            "Table auto-freed on order complete", tbl_data["status"] if tbl_data else "missing")

        # 39. Orders page HTML
        r = await c.get("/orders")
        (ok if r.status_code == 200 else fail)("GET /orders page = 200", r.status_code)
        (ok if "cart-list" in r.text else fail)("Orders page has cart-list div",
            "found" if "cart-list" in r.text else "MISSING")

        # --- Kitchen ---
        # 40. Create a fresh order + items + KOT for kitchen tests
        r = await c.post("/api/orders",
                         json={"order_type": "dine_in", "table_id": order_tbl_id},
                         headers=headers)
        kot_order_id = r.json()["id"]
        await c.post(f"/api/orders/{kot_order_id}/items",
                     json={"menu_item_id": avail_item_id, "quantity": 2},
                     headers=headers)
        r = await c.post(f"/api/orders/{kot_order_id}/kot", headers=headers)
        (ok if r.status_code == 200 else fail)("Setup KOT for kitchen tests = 200", r.status_code)
        kot_num = r.json()["kot_number"]

        # 41. Kitchen tickets list
        r = await c.get("/api/kitchen/tickets", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/kitchen/tickets = 200", r.status_code)
        tickets = r.json()
        ok("Kitchen tickets count", len(tickets))

        # 42. Ticket has correct structure
        ticket = next((t for t in tickets if t["order_id"] == kot_order_id), None)
        (ok if ticket else fail)("Ticket found for new order", str(ticket is not None))
        (ok if ticket and len(ticket["items"]) == 1 else fail)(
            "Ticket has 1 item", len(ticket["items"]) if ticket else 0)

        # 43. Ticket count endpoint
        r = await c.get("/api/kitchen/tickets/count")
        (ok if r.status_code == 200 else fail)("GET /api/kitchen/tickets/count = 200", r.status_code)
        ok("Active kitchen items count", r.json()["active_items"])

        # 44. Bump item: sent → preparing
        oi_id_k = ticket["items"][0]["id"]
        r = await c.patch(f"/api/kitchen/items/{oi_id_k}/bump", headers=headers)
        (ok if r.status_code == 200 else fail)("PATCH /kitchen/items/{id}/bump = 200", r.status_code)
        (ok if r.json()["kot_status"] == "preparing" else fail)(
            "Item bumped to preparing", r.json()["kot_status"])

        # 45. Bump again: preparing → ready
        r = await c.patch(f"/api/kitchen/items/{oi_id_k}/bump", headers=headers)
        (ok if r.json()["kot_status"] == "ready" else fail)(
            "Item bumped to ready", r.json()["kot_status"])

        # 46. bump-all: all ready → served
        r = await c.patch(f"/api/kitchen/tickets/{kot_order_id}/{kot_num}/bump-all",
                          headers=headers)
        (ok if r.status_code == 200 else fail)("PATCH kitchen bump-all = 200", r.status_code)
        (ok if r.json()["served"] == 1 else fail)("1 item served", r.json()["served"])

        # 47. Ticket should now be gone from kitchen
        r = await c.get("/api/kitchen/tickets", headers=headers)
        remaining = [t for t in r.json() if t["order_id"] == kot_order_id]
        (ok if len(remaining) == 0 else fail)("Ticket cleared after serve", len(remaining))

        # 48. Set status directly
        r = await c.patch(f"/api/kitchen/items/{oi_id_k}/status",
                          json={"kot_status": "sent"}, headers=headers)
        (ok if r.status_code == 200 else fail)("PATCH kitchen items status direct = 200", r.status_code)
        (ok if r.json()["kot_status"] == "sent" else fail)(
            "Status set to sent", r.json()["kot_status"])

        # 49. Kitchen page HTML
        r = await c.get("/kitchen")
        (ok if r.status_code == 200 else fail)("GET /kitchen page = 200", r.status_code)
        (ok if "tickets-grid" in r.text else fail)("Kitchen page has tickets-grid div",
            "found" if "tickets-grid" in r.text else "MISSING")

        # --- Billing ---
        # 50. Create a fresh billable order (active with items)
        r = await c.post("/api/orders",
                         json={"order_type": "dine_in", "table_id": order_tbl_id},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("Create order for billing test = 201", r.status_code)
        bill_order_id = r.json()["id"]

        await c.post(f"/api/orders/{bill_order_id}/items",
                     json={"menu_item_id": avail_item_id, "quantity": 2},
                     headers=headers)

        # 51. Generate bill
        r = await c.post("/api/billing/bills",
                         json={"order_id": bill_order_id, "include_service_charge": True},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("POST /api/billing/bills = 201", r.status_code)
        bill = r.json()
        bill_id = bill["id"]
        ok("Bill number generated", bill["bill_number"])
        ok("Fiscal year set", bill["fiscal_year"])
        ok("VAT calculated", f"NPR {bill['vat_amount']}")
        ok("Service charge calculated", f"NPR {bill['service_charge']}")
        ok("Grand total correct",
           f"NPR {bill['grand_total']} (subtotal={bill['subtotal']})")

        # 52. Duplicate bill for same order = 409
        r = await c.post("/api/billing/bills",
                         json={"order_id": bill_order_id},
                         headers=headers)
        (ok if r.status_code == 409 else fail)("Duplicate bill = 409", r.status_code)

        # 53. Get bill by order
        r = await c.get(f"/api/billing/bills/by-order/{bill_order_id}", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /billing/bills/by-order/{id} = 200", r.status_code)
        ok("Bill retrieved by order", r.json()["bill_number"])

        # 54. List bills
        r = await c.get("/api/billing/bills", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/billing/bills = 200", r.status_code)
        ok("Bills list count", len(r.json()))

        # 55. Update bill (discount)
        r = await c.patch(f"/api/billing/bills/{bill_id}/update",
                          json={"discount_type": "flat", "discount_value": 50},
                          headers=headers)
        (ok if r.status_code == 200 else fail)("PATCH bill update discount = 200", r.status_code)
        (ok if r.json()["discount_amount"] == 50.0 else fail)(
            "Discount applied", r.json()["discount_amount"])

        # 56. Record print
        r = await c.patch(f"/api/billing/bills/{bill_id}/print", headers=headers)
        (ok if r.status_code == 200 else fail)("PATCH bill print = 200", r.status_code)
        (ok if r.json()["print_count"] == 1 else fail)("Print count = 1", r.json()["print_count"])

        # 57. Pay bill
        r = await c.post(f"/api/billing/bills/{bill_id}/pay",
                         json={"payment_method": "cash", "amount_tendered": 1000},
                         headers=headers)
        (ok if r.status_code == 200 else fail)("POST bill pay = 200", r.status_code)
        paid = r.json()
        (ok if paid["payment_status"] == "paid" else fail)("Bill status = paid", paid["payment_status"])
        ok("Change calculated", f"NPR {paid.get('change', '—')}")

        # 58. Double-pay rejected
        r = await c.post(f"/api/billing/bills/{bill_id}/pay",
                         json={"payment_method": "cash"},
                         headers=headers)
        (ok if r.status_code == 400 else fail)("Double-pay = 400", r.status_code)

        # 59. Today summary
        r = await c.get("/api/billing/summary/today", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /billing/summary/today = 200", r.status_code)
        s = r.json()
        ok("Today sales total", f"NPR {s['total_sales']}")
        ok("Today VAT collected", f"NPR {s['total_vat_collected']}")

        # 60. Billing page HTML
        r = await c.get("/billing")
        (ok if r.status_code == 200 else fail)("GET /billing page = 200", r.status_code)
        (ok if "payment-section" in r.text else fail)("Billing page has payment-section",
            "found" if "payment-section" in r.text else "MISSING")

        # --- Inventory ---
        # 61. Inventory summary (empty)
        r = await c.get("/api/inventory/summary", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/inventory/summary = 200", r.status_code)
        ok("Summary total_ingredients", r.json()["total_ingredients"])

        # 62. Create ingredient
        r = await c.post("/api/inventory/ingredients",
                         json={"name": "Chicken", "unit": "kg",
                               "current_stock": 5.0, "minimum_stock": 2.0,
                               "cost_per_unit": 400.0},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("POST /api/inventory/ingredients = 201", r.status_code)
        ing_id = r.json()["id"]
        ok("Ingredient created", r.json()["name"])

        # 63. List ingredients
        r = await c.get("/api/inventory/ingredients", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/inventory/ingredients = 200", r.status_code)
        ok("Ingredients count", len(r.json()))

        # 64. Update ingredient
        r = await c.put(f"/api/inventory/ingredients/{ing_id}",
                        json={"minimum_stock": 3.0}, headers=headers)
        (ok if r.status_code == 200 else fail)("PUT /api/inventory/ingredients/{id} = 200", r.status_code)
        (ok if r.json()["minimum_stock"] == 3.0 else fail)(
            "Minimum stock updated", r.json()["minimum_stock"])

        # 65. Low stock flag (stock=5, min=3 → not low; set min=6 to trigger)
        await c.put(f"/api/inventory/ingredients/{ing_id}",
                    json={"minimum_stock": 6.0}, headers=headers)
        r = await c.get(f"/api/inventory/ingredients/{ing_id}", headers=headers)
        (ok if r.json()["is_low_stock"] else fail)("Low stock flag set", r.json()["is_low_stock"])

        # 66. Restock ingredient
        r = await c.post(f"/api/inventory/ingredients/{ing_id}/restock",
                         json={"ingredient_id": ing_id, "quantity": 10.0,
                               "cost_per_unit": 380.0, "supplier_name": "Farm Direct"},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("POST restock = 201", r.status_code)
        new_stock = r.json()["ingredient"]["current_stock"]
        (ok if new_stock == 15.0 else fail)("Stock added correctly", new_stock)

        # 67. Purchase history
        r = await c.get(f"/api/inventory/ingredients/{ing_id}/purchases", headers=headers)
        (ok if r.status_code == 200 else fail)("GET purchase history = 200", r.status_code)
        ok("Purchase records", len(r.json()))

        # 68. Add recipe ingredient
        r = await c.post(f"/api/inventory/recipes/{avail_item_id}",
                         json={"ingredient_id": ing_id, "quantity_used": 0.25, "unit": "kg"},
                         headers=headers)
        (ok if r.status_code == 201 else fail)("POST recipe ingredient = 201", r.status_code)
        recipe_row_id = r.json()["id"]
        ok("Recipe row created", recipe_row_id)

        # 69. Duplicate recipe ingredient = 409
        r = await c.post(f"/api/inventory/recipes/{avail_item_id}",
                         json={"ingredient_id": ing_id, "quantity_used": 0.1, "unit": "kg"},
                         headers=headers)
        (ok if r.status_code == 409 else fail)("Duplicate recipe ingredient = 409", r.status_code)

        # 70. Get recipe with profit calc
        r = await c.get(f"/api/inventory/recipes/{avail_item_id}", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/inventory/recipes/{id} = 200", r.status_code)
        recipe = r.json()
        ok("Recipe cost calculated", f"NPR {recipe['total_cost']}")
        ok("Recipe margin", f"{recipe['margin_percent']}%")

        # 71. Update recipe ingredient qty
        r = await c.put(f"/api/inventory/recipes/items/{recipe_row_id}",
                        json={"quantity_used": 0.5}, headers=headers)
        (ok if r.status_code == 200 else fail)("PUT recipe item = 200", r.status_code)
        (ok if r.json()["quantity_used"] == 0.5 else fail)(
            "Recipe qty updated", r.json()["quantity_used"])

        # 72. Profit report
        r = await c.get("/api/inventory/profit-report", headers=headers)
        (ok if r.status_code == 200 else fail)("GET /api/inventory/profit-report = 200", r.status_code)
        ok("Profit report items", len(r.json()))

        # 73. Low stock filter
        r = await c.get("/api/inventory/ingredients?low_stock_only=true", headers=headers)
        (ok if r.status_code == 200 else fail)("GET ingredients?low_stock_only=true = 200", r.status_code)
        ok("Low stock items returned", len(r.json()))

        # 74. Remove recipe ingredient
        r = await c.delete(f"/api/inventory/recipes/items/{recipe_row_id}", headers=headers)
        (ok if r.status_code == 204 else fail)("DELETE recipe item = 204", r.status_code)

        # 75. Delete ingredient
        r = await c.delete(f"/api/inventory/ingredients/{ing_id}", headers=headers)
        (ok if r.status_code == 204 else fail)("DELETE ingredient = 204", r.status_code)

        # 76. Inventory page HTML
        r = await c.get("/inventory")
        (ok if r.status_code == 200 else fail)("GET /inventory page = 200", r.status_code)
        (ok if "ing-body" in r.text else fail)("Inventory page has ing-body table",
            "found" if "ing-body" in r.text else "MISSING")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


asyncio.run(run())
