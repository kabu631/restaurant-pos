from sqlalchemy import Column, Integer, Float, String, ForeignKey
from app.database import Base


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=False)
    quantity_used = Column(Float, nullable=False)   # Amount used per serving
    unit = Column(String, nullable=False)           # g, ml, piece, etc.
