from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required
from app import db
from app.models.transaction import Transaction
from app.models.customer import Customer
from app.models.product import Product
from app.services.transaction_service import update_transaction, TransactionError
from app.services.dashboard_service import get_sales_transactions, get_expense_transactions

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@bp.route("/")
@login_required
def index():
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template(
        "transactions/index.html",
        sales=get_sales_transactions(),
        expenses=get_expense_transactions(),
        customers=customers,
        products=products,
    )


@bp.route("/<int:tx_id>/edit", methods=["POST"])
@login_required
def edit(tx_id):
    tx = db.get_or_404(Transaction, tx_id)
    if tx.transaction_type != "sale":
        abort(403)
    try:
        update_transaction(
            tx=tx,
            items_raw=request.form.get("items", "[]"),
            customer_id=request.form.get("customer_id") or None,
            payment_status=request.form.get("payment_status"),
            amount_paid_raw=request.form.get("amount_paid", "0"),
        )
    except TransactionError as e:
        category = "warning" if "at least one" in str(e).lower() else "danger"
        flash(str(e), category)
        return redirect(url_for("transactions.index"))

    flash("Transaction updated.", "success")
    return redirect(url_for("transactions.index"))
