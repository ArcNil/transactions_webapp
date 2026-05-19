import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from app.models.product import Product
from app.models.stock import ProductIngredient
from app.models.customer import Customer
from app.services.transaction_service import create_transaction, TransactionError
from app.services.ledger_service import add_entry
from app.utils.monitor import record_action

logger = logging.getLogger(__name__)

bp = Blueprint("pos", __name__, url_prefix="/pos")


@bp.route("/")
@login_required
def index():
    products = (
        Product.query
        .filter_by(is_active=True, show_in_pos=True)
        .options(joinedload(Product.ingredients).joinedload(ProductIngredient.stock_item))
        .order_by(Product.name)
        .all()
    )
    customers = Customer.query.order_by(Customer.name).all()
    customers_json = [{"id": c.id, "name": c.name} for c in customers]
    return render_template("pos/index.html", products=products, customers=customers_json)


@bp.route("/save", methods=["POST"])
@login_required
def save():
    try:
        tx = create_transaction(
            items_raw=request.form.get("items", "[]"),
            customer_id=request.form.get("customer_id") or None,
        )
    except TransactionError as e:
        category = "warning" if "empty" in str(e).lower() else "danger"
        flash(str(e), category)
        return redirect(url_for("pos.index"))

    # Record initial payment as ledger entries if provided.
    payment_status = request.form.get("payment_status", "unpaid")
    amount_paid_raw = request.form.get("amount_paid", "0")
    amount_tendered_raw = request.form.get("amount_tendered") or None

    if amount_tendered_raw:
        # Customer paid cash — record the tendered amount as a payment entry,
        # then close the transaction immediately (no change entry is created).
        try:
            tendered = Decimal(amount_tendered_raw)
            if tendered > 0:
                add_entry(tx, "payment", str(tendered))
            # Close regardless of exact change; cash sales are settled on the spot.
            if tendered >= Decimal(str(tx.total_amount)):
                from app import db
                tx.closed_at = datetime.now(timezone.utc)
                db.session.commit()
        except (InvalidOperation, Exception):
            logger.warning(
                "Failed to record cash ledger entries for POS transaction %s",
                tx.id, exc_info=True,
            )
    elif payment_status in ("full", "partial"):
        paid = str(tx.total_amount) if payment_status == "full" else amount_paid_raw
        try:
            paid_decimal = Decimal(paid)
            if paid_decimal > 0:
                add_entry(tx, "payment", paid)
        except (InvalidOperation, Exception):
            logger.warning(
                "Failed to record payment entry for POS transaction %s",
                tx.id, exc_info=True,
            )

    record_action(current_user.id, current_user.username, "transaction.created")
    flash("Transaction saved!", "success")
    return redirect(url_for("pos.index"))
