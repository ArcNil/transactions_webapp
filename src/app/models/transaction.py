from decimal import Decimal

from app import db
from datetime import datetime, timezone
from sqlalchemy.orm import validates


class Transaction(db.Model):
    __tablename__ = "transactions"

    VALID_TYPES = ("sale", "restock", "stock_restock", "product_restock")

    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(16), nullable=False)  # sale | restock | stock_restock | product_restock — enforced by VALID_TYPES
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    # NULL = open; non-null = closed (manually or auto-closed when balance reaches 0)
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    customer = db.relationship("Customer", back_populates="transactions")
    vendor = db.relationship("Vendor", back_populates="transactions")
    items = db.relationship("TransactionItem", back_populates="transaction", cascade="all, delete-orphan")
    ledger_entries = db.relationship(
        "TransactionLedgerEntry",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="TransactionLedgerEntry.created_at",
    )

    @validates("transaction_type")
    def validate_transaction_type(self, key, value):
        if value not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid transaction_type '{value}'. Must be one of: {self.VALID_TYPES}"
            )
        return value

    # ------------------------------------------------------------------
    # Derived payment properties — computed from the ledger, not stored.
    # ------------------------------------------------------------------

    @property
    def total_paid(self) -> Decimal:
        """Sum of all 'payment' ledger entries."""
        return sum(
            (e.amount for e in self.ledger_entries if e.entry_type == "payment"),
            Decimal("0"),
        )

    @property
    def total_returned(self) -> Decimal:
        """Sum of change + refund + discount entries (excludes adjustments)."""
        RETURN_TYPES = {"change", "refund", "discount"}
        return sum(
            (e.amount for e in self.ledger_entries if e.entry_type in RETURN_TYPES),
            Decimal("0"),
        )

    @property
    def balance(self) -> Decimal:
        """
        Net balance relative to the transaction total.

        balance = total_paid − total_returned + adjustments − total_amount
            Positive  → overpaid (customer is owed money back).
            Zero      → settled.
            Negative  → balance owed (customer still owes).

        Positive adjustments credit the customer (reduce what they owe).
        Negative adjustments charge the customer (increase what they owe).
        """
        adj = sum(
            (e.amount for e in self.ledger_entries if e.entry_type == "adjustment"),
            Decimal("0"),
        )
        return self.total_paid - self.total_returned + adj - Decimal(str(self.total_amount))

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    @property
    def effective_status(self) -> str:
        """Human-readable payment status derived from the ledger."""
        if self.is_closed:
            return "Closed"
        b = self.balance
        if b > 0:
            return "Overpaid"
        if b < 0:
            return "Balance owed"
        return "Settled"


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


class TransactionLedgerEntry(db.Model):
    __tablename__ = "transaction_ledger_entries"

    VALID_TYPES = ("payment", "change", "refund", "discount", "adjustment")

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(
        db.Integer, db.ForeignKey("transactions.id"), nullable=False, index=True
    )
    # entry_type determines whether the amount credits (+) or debits (-) the balance.
    # payment       → credits the customer's debt (reduces balance owed)
    # change        → debit against payment (returns money to customer)
    # refund        → same effect as change but for post-sale returns
    # discount      → reduces the effective balance owed without cash exchange
    # adjustment    → signed; positive = credit to customer, negative = extra charge
    entry_type = db.Column(db.String(16), nullable=False)
    # Always stored as a positive value for all types except 'adjustment'.
    # 'adjustment' may be negative to represent an extra charge.
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    transaction = db.relationship("Transaction", back_populates="ledger_entries")

    @validates("entry_type")
    def validate_entry_type(self, key, value):
        if value not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid entry_type '{value}'. Must be one of: {self.VALID_TYPES}"
            )
        return value
