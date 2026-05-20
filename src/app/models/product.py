import math
from app import db
from datetime import datetime, timezone


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    # 'sale'     → sold through POS; stock decreases on each sale
    # 'purchase' → restockable raw material; stock increases on restock
    product_type = db.Column(db.String(16), nullable=False, default="sale")
    unit = db.Column(db.String(64), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    show_in_pos = db.Column(db.Boolean, default=True, nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)
    photo_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    vendor = db.relationship("Vendor", back_populates="products")
    ingredients = db.relationship("ProductIngredient", back_populates="product", cascade="all, delete-orphan")

    @property
    def available_stock(self):
        """Derived availability: from raw stock if ingredients exist, else direct stock."""
        if not self.ingredients:
            return self.stock
        units = [
            math.floor(float(ing.stock_item.quantity) / float(ing.quantity))
            for ing in self.ingredients
            if ing.quantity > 0
        ]
        return min(units) if units else 0
