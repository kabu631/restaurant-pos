from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.menu import STATIONS, Category, MenuItem
from app.models.inventory import Ingredient
from app.models.recipe import RecipeIngredient
from app.models.user import User
from app.services import audit
from app.services.permissions import require_perm
from app.routes.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/menu", tags=["menu"])


# --- Schemas ---

class CategoryCreate(BaseModel):
    name: str
    display_order: int = 0
    is_active: bool = True
    station: str = "kitchen"        # kitchen / bar / none (served without a ticket)

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    station: Optional[str] = None

class MenuItemCreate(BaseModel):
    category_id: int
    name: str
    name_np: Optional[str] = None
    price: float
    variant_type: Optional[str] = None
    description: Optional[str] = None
    is_vat_applicable: bool = True
    is_available: bool = True
    image_path: Optional[str] = None
    display_order: int = 0

class MenuItemUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    name_np: Optional[str] = None
    price: Optional[float] = None
    variant_type: Optional[str] = None
    description: Optional[str] = None
    is_vat_applicable: Optional[bool] = None
    is_available: Optional[bool] = None
    image_path: Optional[str] = None
    display_order: Optional[int] = None


def _check_category(name: Optional[str], station: Optional[str]):
    if name is not None and not name.strip():
        raise HTTPException(status_code=400, detail="Category name is required")
    if station is not None and station not in STATIONS:
        raise HTTPException(status_code=400, detail=f"station must be one of {list(STATIONS)}")


def _check_item(name: Optional[str], price: Optional[float]):
    if name is not None and not name.strip():
        raise HTTPException(status_code=400, detail="Item name is required")
    if price is not None and price < 0:
        raise HTTPException(status_code=400, detail="Price cannot be negative")


# --- Category endpoints ---

@router.get("/categories")
def list_categories(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    q = db.query(Category)
    if current_user.restaurant_id:
        q = q.filter(Category.restaurant_id == current_user.restaurant_id)
    return q.order_by(Category.display_order, Category.id).all()


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
    _check_category(body.name, body.station)
    body.name = body.name.strip()
    cat = Category(**body.model_dump(), restaurant_id=current_user.restaurant_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/categories/{cat_id}")
def update_category(cat_id: int, body: CategoryUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_admin)):
    _check_category(body.name, body.station)
    q = db.query(Category).filter(Category.id == cat_id)
    if current_user.restaurant_id:
        q = q.filter(Category.restaurant_id == current_user.restaurant_id)
    cat = q.first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    return cat


# --- Menu item endpoints ---

@router.get("/items")
def list_items(category_id: Optional[int] = None, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    q = db.query(MenuItem)
    if current_user.restaurant_id:
        q = q.filter(MenuItem.restaurant_id == current_user.restaurant_id)
    if category_id:
        q = q.filter(MenuItem.category_id == category_id)
    return q.order_by(MenuItem.category_id, MenuItem.display_order, MenuItem.id).all()


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(body: MenuItemCreate, db: Session = Depends(get_db),
                current_user: User = Depends(require_admin)):
    _check_item(body.name, body.price)
    body.name = body.name.strip()
    q = db.query(Category).filter(Category.id == body.category_id)
    if current_user.restaurant_id:
        q = q.filter(Category.restaurant_id == current_user.restaurant_id)
    if not q.first():
        raise HTTPException(status_code=404, detail="Category not found")
    item = MenuItem(**body.model_dump(), restaurant_id=current_user.restaurant_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/items/{item_id}")
def update_item(item_id: int, body: MenuItemUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(require_admin)):
    _check_item(body.name, body.price)
    q = db.query(MenuItem).filter(MenuItem.id == item_id)
    if current_user.restaurant_id:
        q = q.filter(MenuItem.restaurant_id == current_user.restaurant_id)
    item = q.first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    if body.category_id is not None and body.category_id != item.category_id:
        cq = db.query(Category).filter(Category.id == body.category_id,
                                       Category.restaurant_id == item.restaurant_id)
        if not cq.first():
            raise HTTPException(status_code=404, detail="Category not found")
    if body.price is not None and body.price != item.price:
        audit.record(db, current_user, "PRICE_CHANGE", "menu_items", item.id,
                     {"name": item.name, "price": body.price}, old={"price": item.price})
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/items/{item_id}/toggle")
def toggle_availability(item_id: int, db: Session = Depends(get_db),
                        current_user: User = Depends(require_perm("menu.availability"))):
    q = db.query(MenuItem).filter(MenuItem.id == item_id)
    if current_user.restaurant_id:
        q = q.filter(MenuItem.restaurant_id == current_user.restaurant_id)
    item = q.first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    item.is_available = not item.is_available
    audit.record(db, current_user, "BACK_ON_MENU" if item.is_available else "SOLD_OUT",
                 "menu_items", item.id, {"name": item.name})
    db.commit()
    return {"id": item.id, "is_available": item.is_available}


@router.get("/items/{item_id}/profit")
def get_item_profit(item_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    q = db.query(MenuItem).filter(MenuItem.id == item_id)
    if current_user.restaurant_id:
        q = q.filter(MenuItem.restaurant_id == current_user.restaurant_id)
    item = q.first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    recipes = db.query(RecipeIngredient).filter(
        RecipeIngredient.menu_item_id == item_id
    ).all()

    cost = 0.0
    breakdown = []
    for r in recipes:
        ing = db.query(Ingredient).filter(Ingredient.id == r.ingredient_id).first()
        if ing:
            line_cost = r.quantity_used * ing.cost_per_unit
            cost += line_cost
            breakdown.append({
                "ingredient": ing.name,
                "quantity": r.quantity_used,
                "unit": r.unit,
                "cost_per_unit": ing.cost_per_unit,
                "line_cost": round(line_cost, 2),
            })

    profit = item.price - cost
    margin = (profit / item.price * 100) if item.price > 0 else 0

    return {
        "item_id": item.id,
        "name": item.name,
        "selling_price": item.price,
        "cost_to_make": round(cost, 2),
        "profit_per_dish": round(profit, 2),
        "margin_percent": round(margin, 1),
        "is_low_margin": margin < 30,
        "ingredients": breakdown,
    }
