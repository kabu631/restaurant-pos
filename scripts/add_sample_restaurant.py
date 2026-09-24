"""
Add a "Sample Restaurant" (login code: sample) with a full menu, 14 tables and staff,
for trying the POS without touching your real restaurant.  Safe to run once;
it does nothing if the code is already taken.

    python scripts/add_sample_restaurant.py

Logins (restaurant code "sample"): admin / admin123 (PIN 0000), cashier1 (PIN 1111),
waiter1 (PIN 2222), kitchen1 (PIN 3333).  Remove it later from the superadmin page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: E402,F401
from app.database import SessionLocal, create_tables  # noqa: E402
from app.models.restaurant import Restaurant  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import demo_data  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

CODE = "sample"


def main():
    create_tables()
    db = SessionLocal()
    try:
        if db.query(Restaurant).filter(Restaurant.slug == CODE).first():
            print(f"Restaurant code '{CODE}' already exists — nothing to do.")
            return
        r = Restaurant(name="Sample Restaurant", slug=CODE, is_active=True,
                       address="Thamel, Kathmandu", phone="01-4400000")
        db.add(r)
        db.flush()
        db.add(User(restaurant_id=r.id, username="admin", password_hash=hash_password("admin123"),
                    full_name="Sample Admin", role="admin", is_active=True, pin="0000"))
        demo_data.populate(db, r.id)
        db.commit()
        print(f"Added 'Sample Restaurant' — log in with restaurant code '{CODE}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
