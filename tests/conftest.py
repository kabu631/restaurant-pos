"""
Test setup: every run uses a throwaway SQLite database in a temp folder, so the
real restaurant database (PostgreSQL) and data/backups are never touched.

Run:  python -m pytest -q
To test against PostgreSQL, point POS_TEST_DATABASE_URL at an EMPTY scratch database
(never the live one):  POS_TEST_DATABASE_URL=postgresql://postgres:pw@localhost/pos_test
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

# Must be set before anything imports app.config / app.database
_TMP = Path(tempfile.mkdtemp(prefix="pos-tests-"))
os.environ["DATABASE_URL"] = (os.environ.get("POS_TEST_DATABASE_URL")
                              or f"sqlite:///{(_TMP / 'test.db').as_posix()}")
os.environ["POS_DATA_DIR"] = str(_TMP / "data")
os.environ["BACKUP_ENABLED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, username, password, code="demo"):
    r = client.post("/api/auth/login",
                    json={"username": username, "password": password, "restaurant_code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin", "admin123")


@pytest.fixture(scope="session")
def cashier(client):
    return _login(client, "cashier1", "cash123")


@pytest.fixture(scope="session")
def waiter(client):
    return _login(client, "waiter1", "wait123")


@pytest.fixture(scope="session")
def kitchen(client):
    return _login(client, "kitchen1", "kit123")


@pytest.fixture(scope="session")
def menu(client, admin):
    """Demo menu by name → item dict."""
    return {i["name"]: i for i in client.get("/api/menu/items", headers=admin).json()}


@pytest.fixture
def new_table(client, admin):
    """A fresh free table per test so tests never collide."""
    def make(capacity=4, floor="Ground"):
        r = client.post("/api/tables", headers=admin, json={
            "table_number": f"X-{uuid.uuid4().hex[:6]}", "capacity": capacity, "floor": floor})
        assert r.status_code == 201, r.text
        return r.json()
    return make


@pytest.fixture
def open_order(client, waiter, menu, new_table):
    """Open a dine-in order with items (not sent) and return its detail."""
    def make(items=(("Chicken Momo", 1),), send_kot=False, headers=None):
        table = new_table()
        r = client.post("/api/orders", headers=headers or waiter, json={
            "table_id": table["id"], "guests": 2, "send_kot": send_kot,
            "items": [{"menu_item_id": menu[name]["id"], "quantity": qty} for name, qty in items],
        })
        assert r.status_code == 201, r.text
        return r.json()
    return make


@pytest.fixture(scope="session")
def other_restaurant(client):
    """A second tenant with its own admin, for isolation tests."""
    code = f"r{uuid.uuid4().hex[:8]}"
    r = client.post("/api/restaurants/register", json={
        "restaurant_name": "Other Place", "restaurant_code": code,
        "admin_username": "boss", "admin_password": "boss123", "admin_full_name": "Boss",
    })
    assert r.status_code == 201, r.text
    return {"code": code, "headers": _login(client, "boss", "boss123", code)}
