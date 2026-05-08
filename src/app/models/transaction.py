from app import db
from datetime import datetime, timezone
from sqlalchemy.orm import validates


class Transaction(db.Model):
    __tablename__ = "transactions"

    VALID_TYPES = ("sale", "restock", "stock_restock")

    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(16), nullable=False)  # sale | restock | stock_restock — enforced by VALID_TYPES
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_status = db.Column(db.String(16), nullable=False)  # full / partial / unpaid
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    customer = db.relationship("Customer", back_populates="transactions")
    vendor = db.relationship("Vendor", back_populates="transactions")
    items = db.relationship("TransactionItem", back_populates="transaction", cascade="all, delete-orphan")

    @validates("transaction_type")
    def validate_transaction_type(self, key, value):
        if value not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid transaction_type '{value}'. Must be one of: {self.VALID_TYPES}"
            )
        return value


class TransactionItem(db.Model):
    __tablename__ = "transaction_items"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name_snapshot = db.Column(db.String(128), nullable=False)
    unit_snapshot = db.Column(db.String(64), nullable=False)
    unit_price_snapshot = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    # Populated on stock_restock lines; NULL for sale/restock lines
    stock_item_id = db.Column(db.Integer, db.ForeignKey("stock_items.id"), nullable=True)

    transaction = db.relationship("Transaction", back_populates="items")
    product = db.relationship("Product")
    stock_item = db.relationship("StockItem", back_populates="restock_items")
