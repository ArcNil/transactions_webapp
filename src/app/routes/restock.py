import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from decimal import Decimal, InvalidOperation
from app.models.product import Product
from app.services.transaction_service import create_product_restock, TransactionError
from app.services.ledger_service import add_entry, LedgerError
from app.utils.monitor import record_action

logger = logging.getLogger(__name__)

bp = Blueprint("restock", __name__, url_prefix="/restock")


@bp.route("/")
@login_required
def index():
    # Only purchase-type products with a vendor can be restocked.
    products = (
        Product.query
        .filter(Product.product_type == "purchase", Product.vendor_id.isnot(None))
        .order_by(Product.name)
        .all()
    )
    no_vendor_count = (
        Product.query
        .filter(Product.product_type == "purchase", Product.vendor_id.is_(None))
        .count()
    )
    return render_template(
        "restock/index.html",
        products=products,
        no_vendor_count=no_vendor_count,
    )


@bp.route("/save", methods=["POST"])
@login_required
def save():
    try:
        tx = create_product_restock(
            items_raw=request.form.get("items", "[]"),
        )
    except TransactionError as e:
        flash(str(e), "danger")
        return redirect(url_for("restock.index"))

    # Record initial payment as a ledger entry if provided.
    payment_status = request.form.get("payment_status", "unpaid")
    amount_paid_raw = request.form.get("amount_paid", "0")
    if payment_status in ("full", "partial"):
        paid = str(tx.total_amount) if payment_status == "full" else amount_paid_raw
        try:
            if Decimal(paid) > 0:
                add_entry(tx, "payment", paid)
        except (InvalidOperation, LedgerError):
            logger.warning(
                "Failed to record payment entry for restock %s", tx.id, exc_info=True
            )

    record_action(current_user.id, current_user.username, "restock.created")
    flash("Restock saved!", "success")
    return redirect(url_for("restock.index"))
