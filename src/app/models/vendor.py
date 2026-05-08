from app import db
from datetime import datetime, timezone


class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    products = db.relationship("Product", back_populates="vendor")
    transactions = db.relationship("Transaction", back_populates="vendor")
    stock_items = db.relationship("StockItem", back_populates="vendor")
