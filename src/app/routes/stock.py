import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from decimal import Decimal, InvalidOperation
from app import db
from app.models.stock import StockItem
from app.models.vendor import Vendor
from app.forms.stock import StockItemForm, StockAdjustForm
from app.services.transaction_service import create_stock_restock, TransactionError
from app.services.ledger_service import add_entry
from app.services.stock_service import delete_stock_item, StockError
from app.utils.monitor import record_action

logger = logging.getLogger(__name__)

bp = Blueprint("stock", __name__, url_prefix="/stock")


def _vendor_choices():
    vendors = Vendor.query.order_by(Vendor.name).all()
    return [(0, "— None —")] + [(v.id, v.name) for v in vendors]


@bp.route("/")
@login_required
def index():
    items = StockItem.query.order_by(StockItem.name).all()
    form = StockItemForm()
    form.vendor_id.choices = _vendor_choices()
    adjust_form = StockAdjustForm()
    return render_template("stock/index.html", items=items, form=form, adjust_form=adjust_form)


@bp.route("/add", methods=["POST"])
@login_required
def add():
    form = StockItemForm()
    form.vendor_id.choices = _vendor_choices()
    if form.validate_on_submit():
        item = StockItem(
            name=form.name.data.strip(),
            unit=form.unit.data.strip(),
            vendor_id=form.vendor_id.data if form.vendor_id.data != 0 else None,
        )
        db.session.add(item)
        db.session.commit()
        record_action(current_user.id, current_user.username, "stock_item.added", item.name)
        flash(f'Stock item "{item.name}" added.', "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("stock.index"))


@bp.route("/<int:item_id>/edit", methods=["POST"])
@login_required
def edit(item_id):
    item = db.get_or_404(StockItem, item_id)
    form = StockItemForm()
    form.vendor_id.choices = _vendor_choices()
    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.unit = form.unit.data.strip()
        item.vendor_id = form.vendor_id.data if form.vendor_id.data != 0 else None
        db.session.commit()
        record_action(current_user.id, current_user.username, "stock_item.edited", item.name)
        flash(f'Stock item "{item.name}" updated.', "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("stock.index"))


@bp.route("/<int:item_id>/adjust", methods=["POST"])
@login_required
def adjust(item_id):
    """Manually add quantity to a stock item (admin correction — no vendor purchase record)."""
    item = db.get_or_404(StockItem, item_id)
    form = StockAdjustForm()
    if form.validate_on_submit():
        item.quantity += form.quantity.data
        db.session.commit()
        record_action(current_user.id, current_user.username, "stock_item.adjusted", item.name)
        flash(f'Added {form.quantity.data} {item.unit}(s) to "{item.name}".', "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("stock.index"))


@bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id):
    item = db.get_or_404(StockItem, item_id)
    item_name = item.name
    try:
        delete_stock_item(item, current_user.id, current_user.username)
        flash(f'Stock item "{item_name}" removed.', "success")
    except StockError as e:
        flash(str(e), "warning")
    return redirect(url_for("stock.index"))


@bp.route("/restock")
@login_required
def restock_index():
    items = StockItem.query.order_by(StockItem.name).all()
    vendors = Vendor.query.order_by(Vendor.name).all()
    vendors_json = [{"id": v.id, "name": v.name} for v in vendors]
    return render_template("stock/restock.html", items=items, vendors=vendors_json)


@bp.route("/restock/save", methods=["POST"])
@login_required
def restock_save():
    try:
        tx = create_stock_restock(
            items_raw=request.form.get("items", "[]"),
            vendor_id=request.form.get("vendor_id") or "",
        )
    except TransactionError as e:
        flash(str(e), "danger")
        return redirect(url_for("stock.restock_index"))

    # Record initial payment as a ledger entry if provided.
    payment_status = request.form.get("payment_status", "unpaid")
    amount_paid_raw = request.form.get("amount_paid", "0")
    if payment_status in ("full", "partial"):
        paid = str(tx.total_amount) if payment_status == "full" else amount_paid_raw
        try:
            if Decimal(paid) > 0:
                add_entry(tx, "payment", paid)
        except (InvalidOperation, Exception):
            logger.warning(
                "Failed to record payment entry for stock restock %s", tx.id, exc_info=True
            )

    record_action(current_user.id, current_user.username, "stock.restocked")
    flash("Raw stock restock saved!", "success")
    return redirect(url_for("stock.restock_index"))
