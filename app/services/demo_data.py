"""
Sample menu, tables and staff for the demo restaurant.

Only called when the "demo" restaurant is first created (a brand-new install),
so an existing database is never touched.  Matches the accounts in README.md.
"""
from sqlalchemy.orm import Session

from app.models.menu import Category, MenuItem
from app.models.table import RestaurantTable
from app.models.user import User
from app.utils.security import hash_password

STAFF = [
    # username, password, full name, role, PIN
    ("cashier1", "cash123", "Sita Cashier", "cashier", "1111"),
    ("waiter1",  "wait123", "Ram Waiter",   "waiter",  "2222"),
    ("kitchen1", "kit123",  "Hari Kitchen", "kitchen", "3333"),
]

TABLES = (
    [(f"T{n}", 2 if n <= 2 else 4, "Ground") for n in range(1, 9)]
    + [(f"T{n}", 6, "First") for n in range(9, 13)]
    + [("VIP-1", 8, "Rooftop"), ("VIP-2", 8, "Rooftop")]
)

MENU = [
    # category, station, [(item, price, nepali name)]
    ("Momo & Dumplings", "kitchen", [
        ("Chicken Momo", 250, "चिकेन मम"), ("Veg Momo", 180, "भेज मम"),
        ("Buff Momo", 220, "बफ मम"), ("Jhol Momo", 280, "झोल मम"),
        ("C-Momo", 300, "सी-मम"),
    ]),
    ("Dal Bhat Set", "kitchen", [
        ("Dal Bhat Set Veg", 350, "दाल भात (भेज)"), ("Dal Bhat Set Chicken", 450, "दाल भात (चिकेन)"),
        ("Dal Bhat Set Mutton", 550, "दाल भात (खसी)"),
    ]),
    ("Noodles & Rice", "kitchen", [
        ("Chicken Chowmein", 200, "चिकेन चाउमिन"), ("Veg Chowmein", 160, "भेज चाउमिन"),
        ("Fried Rice Chicken", 280, "चिकेन फ्राइड राइस"), ("Fried Rice Veg", 220, "भेज फ्राइड राइस"),
        ("Thukpa", 240, "थुक्पा"),
    ]),
    ("Grill & Starters", "kitchen", [
        ("Chicken Sekuwa", 400, "चिकेन सेकुवा"), ("Paneer Tikka", 350, "पनिर टिक्का"),
        ("Chicken Choila", 380, "चिकेन छोयला"), ("French Fries", 180, "फ्रेन्च फ्राइज"),
    ]),
    ("Hot Drinks", "bar", [
        ("Milk Tea", 40, "दुध चिया"), ("Lemon Tea", 60, "लेमन टी"),
        ("Black Coffee", 120, "कालो कफी"), ("Cappuccino", 180, "क्यापुचिनो"),
    ]),
    ("Cold Drinks", "none", [
        ("Coke", 80, "कोक"), ("Fanta", 80, "फान्टा"), ("Mineral Water", 40, "पानी"),
    ]),
    ("Desserts", "kitchen", [
        ("Kheer", 120, "खिर"), ("Gulab Jamun", 150, "गुलाब जामुन"),
    ]),
]


def populate(db: Session, restaurant_id: int) -> None:
    for username, password, full_name, role, pin in STAFF:
        db.add(User(restaurant_id=restaurant_id, username=username,
                    password_hash=hash_password(password), full_name=full_name,
                    role=role, is_active=True, pin=pin))

    for number, capacity, floor in TABLES:
        db.add(RestaurantTable(restaurant_id=restaurant_id, table_number=number,
                               capacity=capacity, floor=floor, status="free"))

    for order, (cat_name, station, items) in enumerate(MENU, start=1):
        cat = Category(restaurant_id=restaurant_id, name=cat_name, display_order=order,
                       is_active=True, station=station)
        db.add(cat)
        db.flush()
        for pos, (name, price, name_np) in enumerate(items, start=1):
            db.add(MenuItem(restaurant_id=restaurant_id, category_id=cat.id, name=name,
                            name_np=name_np, price=float(price), display_order=pos,
                            is_vat_applicable=True, is_available=True))
