from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.product import Product
from app.models.vendor import Vendor
from app.services.transaction_service import create_restock, TransactionError
from app.utils.monitor import record_action

bp = Blueprint("restock", __name__, url_prefix="/restock")


@bp.route("/")
@login_required
def index():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    vendors = Vendor.query.order_by(Vendor.name).all()
    vendors_json = [{"id": v.id, "name": v.name} for v in vendors]
    return render_template("restock/index.html", products=products, vendors=vendors_json)


@bp.route("/save", methods=["POST"])
@login_required
def save():
    try:
        create_restock(
            items_raw=request.form.get("items", "[]"),
            vendor_id=request.form.get("vendor_id") or "",
            payment_status=request.form.get("payment_status"),
            amount_paid_raw=request.form.get("amount_paid", "0"),
        )
    except TransactionError as e:
        flash(str(e), "danger")
        return redirect(url_for("restock.index"))

    record_action(current_user.id, current_user.username, "restock.created")
    flash("Restock saved!", "success")
    return redirect(url_for("restock.index"))
