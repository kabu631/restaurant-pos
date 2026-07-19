import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db, db_transaction

_log = logging.getLogger(__name__)
from app.models.inventory import Ingredient, StockPurchase
from app.models.recipe import RecipeIngredient
from app.models.menu import MenuItem
from app.models.user import User
from app.routes.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


# --- Schemas ---

class IngredientCreate(BaseModel):
    name: str
    unit: str
    current_stock: float = 0.0
    minimum_stock: float = 0.0
    cost_per_unit: float = 0.0
    supplier_name: Optional[str] = None

class IngredientUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    minimum_stock: Optional[float] = None
    cost_per_unit: Optional[float] = None
    supplier_name: Optional[str] = None

class StockPurchaseCreate(BaseModel):
    ingredient_id: int
    quantity: float
    cost_per_unit: float
    supplier_name: Optional[str] = None

class RecipeIngredientCreate(BaseModel):
    ingredient_id: int
    quantity_used: float
    unit: str

class RecipeIngredientUpdate(BaseModel):
    quantity_used: Optional[float] = None
    unit: Optional[str] = None


# --- Helpers ---

def _ingredient_detail(ing: Ingredient) -> dict:
    low_stock = ing.current_stock <= ing.minimum_stock and ing.minimum_stock > 0
    return {
        "id": ing.id,
        "name": ing.name,
        "unit": ing.unit,
        "current_stock": ing.current_stock,
        "minimum_stock": ing.minimum_stock,
        "cost_per_unit": ing.cost_per_unit,
        "supplier_name": ing.supplier_name,
        "stock_value": round(ing.current_stock * ing.cost_per_unit, 2),
        "is_low_stock": low_stock,
        "last_purchased_at": ing.last_purchased_at.isoformat() if ing.last_purchased_at else None,
    }


# --- Ingredient endpoints ---

@router.get("/ingredients")
def list_ingredients(low_stock_only: bool = False, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin)):
    q = db.query(Ingredient)
    if current_user.restaurant_id:
        q = q.filter(Ingredient.restaurant_id == current_user.restaurant_id)
    result = [_ingredient_detail(i) for i in q.order_by(Ingredient.name).all()]
    if low_stock_only:
        result = [i for i in result if i["is_low_stock"]]
    return result


@router.post("/ingredients", status_code=status.HTTP_201_CREATED)
def create_ingredient(body: IngredientCreate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_admin)):
    ing = Ingredient(**body.model_dump(), restaurant_id=current_user.restaurant_id)
    db.add(ing)
    db.commit()
    db.refresh(ing)
    return _ingredient_detail(ing)


@router.get("/ingredients/{ing_id}")
def get_ingredient(ing_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(require_admin)):
    q = db.query(Ingredient).filter(Ingredient.id == ing_id)
    if current_user.restaurant_id:
        q = q.filter(Ingredient.restaurant_id == current_user.restaurant_id)
    ing = q.first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return _ingredient_detail(ing)


@router.put("/ingredients/{ing_id}")
def update_ingredient(ing_id: int, body: IngredientUpdate,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(require_admin)):
    q = db.query(Ingredient).filter(Ingredient.id == ing_id)
    if current_user.restaurant_id:
        q = q.filter(Ingredient.restaurant_id == current_user.restaurant_id)
    ing = q.first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(ing, field, value)
    db.commit()
    db.refresh(ing)
    return _ingredient_detail(ing)


@router.delete("/ingredients/{ing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(ing_id: int, db: Session = Depends(get_db),
                      current_user: User = Depends(require_admin)):
    q = db.query(Ingredient).filter(Ingredient.id == ing_id)
    if current_user.restaurant_id:
        q = q.filter(Ingredient.restaurant_id == current_user.restaurant_id)
    ing = q.first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    db.query(RecipeIngredient).filter(RecipeIngredient.ingredient_id == ing_id).delete()
    db.delete(ing)
    db.commit()


# --- Stock purchase (restock) ---

@router.post("/ingredients/{ing_id}/restock", status_code=status.HTTP_201_CREATED)
def restock(ing_id: int, body: StockPurchaseCreate,
            db: Session = Depends(get_db),
            current_user: User = Depends(require_admin)):
    q = db.query(Ingredient).filter(Ingredient.id == ing_id)
    if current_user.restaurant_id:
        q = q.filter(Ingredient.restaurant_id == current_user.restaurant_id)
    ing = q.first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if body.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    total = round(body.quantity * body.cost_per_unit, 2)

    # Atomic: create purchase record + update stock level together
    with db_transaction(db):
        purchase = StockPurchase(
            ingredient_id=ing_id,
            quantity=body.quantity,
            cost_per_unit=body.cost_per_unit,
            total_cost=total,
            supplier_name=body.supplier_name,
            purchased_by=current_user.id,
        )
        db.add(purchase)
        ing.current_stock = round(ing.current_stock + body.quantity, 4)
        ing.cost_per_unit = body.cost_per_unit
        ing.last_purchased_at = datetime.now(timezone.utc)
        if body.supplier_name:
            ing.supplier_name = body.supplier_name
        db.commit()
        db.refresh(purchase)
        db.refresh(ing)

    return {
        "purchase_id": purchase.id,
        "ingredient": _ingredient_detail(ing),
        "total_cost": total,
    }


@router.get("/ingredients/{ing_id}/purchases")
def purchase_history(ing_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin)):
    q = db.query(Ingredient).filter(Ingredient.id == ing_id)
    if current_user.restaurant_id:
        q = q.filter(Ingredient.restaurant_id == current_user.restaurant_id)
    ing = q.first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    purchases = (db.query(StockPurchase)
                 .filter(StockPurchase.ingredient_id == ing_id)
                 .order_by(StockPurchase.purchased_at.desc())
                 .all())
    return [{"id": p.id, "quantity": p.quantity, "cost_per_unit": p.cost_per_unit,
             "total_cost": p.total_cost, "supplier_name": p.supplier_name,
             "purchased_at": p.purchased_at.isoformat() if p.purchased_at else None}
            for p in purchases]


# --- Recipe management ---

@router.get("/recipes/{menu_item_id}")
def get_recipe(menu_item_id: int, db: Session = Depends(get_db),
               current_user: User = Depends(require_admin)):
    mq = db.query(MenuItem).filter(MenuItem.id == menu_item_id)
    if current_user.restaurant_id:
        mq = mq.filter(MenuItem.restaurant_id == current_user.restaurant_id)
    mi = mq.first()
    if not mi:
        raise HTTPException(status_code=404, detail="Menu item not found")
    rows = db.query(RecipeIngredient).filter(
        RecipeIngredient.menu_item_id == menu_item_id
    ).all()
    ingredients = []
    total_cost = 0.0
    for r in rows:
        ing = db.query(Ingredient).filter(Ingredient.id == r.ingredient_id).first()
        line_cost = round(r.quantity_used * (ing.cost_per_unit if ing else 0), 2)
        total_cost += line_cost
        ingredients.append({
            "id": r.id,
            "ingredient_id": r.ingredient_id,
            "name": ing.name if ing else "Unknown",
            "unit": r.unit,
            "quantity_used": r.quantity_used,
            "cost_per_unit": ing.cost_per_unit if ing else 0,
            "line_cost": line_cost,
        })
    profit = mi.price - total_cost
    margin = round(profit / mi.price * 100, 1) if mi.price > 0 else 0
    return {
        "menu_item_id": mi.id,
        "name": mi.name,
        "selling_price": mi.price,
        "total_cost": round(total_cost, 2),
        "profit": round(profit, 2),
        "margin_percent": margin,
        "is_low_margin": margin < 30,
        "ingredients": ingredients,
    }


@router.post("/recipes/{menu_item_id}", status_code=status.HTTP_201_CREATED)
def add_recipe_ingredient(menu_item_id: int, body: RecipeIngredientCreate,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(require_admin)):
    mq = db.query(MenuItem).filter(MenuItem.id == menu_item_id)
    if current_user.restaurant_id:
        mq = mq.filter(MenuItem.restaurant_id == current_user.restaurant_id)
    if not mq.first():
        raise HTTPException(status_code=404, detail="Menu item not found")
    iq = db.query(Ingredient).filter(Ingredient.id == body.ingredient_id)
    if current_user.restaurant_id:
        iq = iq.filter(Ingredient.restaurant_id == current_user.restaurant_id)
    if not iq.first():
        raise HTTPException(status_code=404, detail="Ingredient not found")
    # Prevent duplicate ingredient in same recipe
    existing = db.query(RecipeIngredient).filter(
        RecipeIngredient.menu_item_id == menu_item_id,
        RecipeIngredient.ingredient_id == body.ingredient_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ingredient already in recipe")

    row = RecipeIngredient(
        menu_item_id=menu_item_id,
        ingredient_id=body.ingredient_id,
        quantity_used=body.quantity_used,
        unit=body.unit,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "menu_item_id": row.menu_item_id,
            "ingredient_id": row.ingredient_id,
            "quantity_used": row.quantity_used, "unit": row.unit}


@router.put("/recipes/items/{row_id}")
def update_recipe_ingredient(row_id: int, body: RecipeIngredientUpdate,
                             db: Session = Depends(get_db),
                             _=Depends(get_current_user)):
    row = db.query(RecipeIngredient).filter(RecipeIngredient.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Recipe ingredient not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "quantity_used": row.quantity_used, "unit": row.unit}


@router.delete("/recipes/items/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_recipe_ingredient(row_id: int, db: Session = Depends(get_db),
                              _=Depends(get_current_user)):
    row = db.query(RecipeIngredient).filter(RecipeIngredient.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Recipe ingredient not found")
    db.delete(row)
    db.commit()


# --- Inventory summary ---

@router.get("/summary")
def inventory_summary(db: Session = Depends(get_db),
                      current_user: User = Depends(require_admin)):
    q = db.query(Ingredient)
    if current_user.restaurant_id:
        q = q.filter(Ingredient.restaurant_id == current_user.restaurant_id)
    ings = q.all()
    total_value = round(sum(i.current_stock * i.cost_per_unit for i in ings), 2)
    low_stock = [_ingredient_detail(i) for i in ings
                 if i.current_stock <= i.minimum_stock and i.minimum_stock > 0]
    return {
        "total_ingredients": len(ings),
        "total_stock_value": total_value,
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock,
    }


# --- Profit report across all menu items ---

@router.get("/profit-report")
def profit_report(db: Session = Depends(get_db),
                  current_user: User = Depends(require_admin)):
    q = db.query(MenuItem).filter(MenuItem.is_available.is_(True))
    if current_user.restaurant_id:
        q = q.filter(MenuItem.restaurant_id == current_user.restaurant_id)
    items = q.all()
    report = []
    for mi in items:
        rows = db.query(RecipeIngredient).filter(
            RecipeIngredient.menu_item_id == mi.id
        ).all()
        cost = sum(r.quantity_used * (
            db.query(Ingredient).filter(Ingredient.id == r.ingredient_id).first()
        ).cost_per_unit
        for r in rows
        if db.query(Ingredient).filter(Ingredient.id == r.ingredient_id).first()
        )
        profit = mi.price - cost
        margin = round(profit / mi.price * 100, 1) if mi.price > 0 else 0
        report.append({
            "menu_item_id": mi.id,
            "name": mi.name,
            "price": mi.price,
            "cost": round(cost, 2),
            "profit": round(profit, 2),
            "margin_percent": margin,
            "is_low_margin": margin < 30,
            "has_recipe": len(rows) > 0,
        })
    report.sort(key=lambda x: x["margin_percent"])
    return report
