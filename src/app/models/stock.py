from app import db
from datetime import datetime, timezone


class StockItem(db.Model):
    __tablename__ = "stock_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    unit = db.Column(db.String(64), nullable=False)
    quantity = db.Column(db.Numeric(10, 4), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    ingredients = db.relationship("ProductIngredient", back_populates="stock_item")
    yields = db.relationship("ProductYield", back_populates="stock_item")
    restock_items = db.relationship("TransactionItem", back_populates="stock_item")


class ProductIngredient(db.Model):
    __tablename__ = "product_ingredients"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    stock_item_id = db.Column(db.Integer, db.ForeignKey("stock_items.id"), nullable=False)
    # How much of the stock item is consumed per 1 unit of the product sold
    quantity = db.Column(db.Numeric(10, 4), nullable=False)

    product = db.relationship("Product", back_populates="ingredients")
    stock_item = db.relationship("StockItem", back_populates="ingredients")


class ProductYield(db.Model):
    """How much of a raw stock item 1 unit of a purchase product adds when restocked."""
    __tablename__ = "product_yields"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    stock_item_id = db.Column(db.Integer, db.ForeignKey("stock_items.id"), nullable=False)
    # How much of the stock item is added per 1 unit of the purchase product restocked
    quantity = db.Column(db.Numeric(10, 4), nullable=False)

    product = db.relationship("Product", back_populates="yields")
    stock_item = db.relationship("StockItem", back_populates="yields")
