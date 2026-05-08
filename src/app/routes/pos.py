from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models.product import Product
from app.models.stock import ProductIngredient
from app.models.customer import Customer
from app.services.transaction_service import create_transaction, TransactionError
from app.utils.monitor import record_action

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
        create_transaction(
            items_raw=request.form.get("items", "[]"),
            customer_id=request.form.get("customer_id") or None,
            payment_status=request.form.get("payment_status"),
            amount_paid_raw=request.form.get("amount_paid", "0"),
        )
    except TransactionError as e:
        category = "warning" if "empty" in str(e).lower() else "danger"
        flash(str(e), category)
        return redirect(url_for("pos.index"))

    record_action(current_user.id, current_user.username, "transaction.created")
    flash("Transaction saved!", "success")
    return redirect(url_for("pos.index"))
