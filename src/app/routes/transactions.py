from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required
from app import db
from app.models.transaction import Transaction, TransactionLedgerEntry
from app.models.customer import Customer
from app.models.product import Product
from app.services.transaction_service import update_transaction, TransactionError
from app.services.ledger_service import (
    add_entry, update_entry, delete_entry,
    close_transaction, reopen_transaction, LedgerError,
)
from app.services.dashboard_service import get_sales_transactions, get_expense_transactions

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@bp.route("/")
@login_required
def index():
    return render_template(
        "transactions/index.html",
        sales=get_sales_transactions(),
        expenses=get_expense_transactions(),
    )


@bp.route("/<int:tx_id>")
@login_required
def detail(tx_id):
    tx = db.get_or_404(Transaction, tx_id)
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template(
        "transactions/detail.html",
        tx=tx,
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
        )
    except TransactionError as e:
        category = "warning" if "at least one" in str(e).lower() else "danger"
        flash(str(e), category)
        return redirect(url_for("transactions.detail", tx_id=tx_id))

    flash("Transaction updated.", "success")
    return redirect(url_for("transactions.detail", tx_id=tx_id))


@bp.route("/<int:tx_id>/ledger", methods=["POST"])
@login_required
def ledger_add(tx_id):
    tx = db.get_or_404(Transaction, tx_id)
    try:
        add_entry(
            tx=tx,
            entry_type=request.form.get("entry_type", ""),
            amount_raw=request.form.get("amount", ""),
            note=request.form.get("note") or None,
        )
    except LedgerError as e:
        flash(str(e), "danger")
        return redirect(url_for("transactions.detail", tx_id=tx_id))

    flash("Entry added.", "success")
    return redirect(url_for("transactions.detail", tx_id=tx_id))


@bp.route("/<int:tx_id>/ledger/<int:entry_id>/edit", methods=["POST"])
@login_required
def ledger_edit(tx_id, entry_id):
    tx = db.get_or_404(Transaction, tx_id)
    entry = db.get_or_404(TransactionLedgerEntry, entry_id)
    if entry.transaction_id != tx.id:
        abort(404)
    try:
        update_entry(
            entry=entry,
            entry_type=request.form.get("entry_type", ""),
            amount_raw=request.form.get("amount", ""),
            note=request.form.get("note") or None,
        )
    except LedgerError as e:
        flash(str(e), "danger")
        return redirect(url_for("transactions.detail", tx_id=tx_id))

    flash("Entry updated.", "success")
    return redirect(url_for("transactions.detail", tx_id=tx_id))


@bp.route("/<int:tx_id>/ledger/<int:entry_id>/delete", methods=["POST"])
@login_required
def ledger_delete(tx_id, entry_id):
    tx = db.get_or_404(Transaction, tx_id)
    entry = db.get_or_404(TransactionLedgerEntry, entry_id)
    if entry.transaction_id != tx.id:
        abort(404)
    try:
        delete_entry(entry)
    except LedgerError as e:
        flash(str(e), "danger")
        return redirect(url_for("transactions.detail", tx_id=tx_id))

    flash("Entry deleted.", "success")
    return redirect(url_for("transactions.detail", tx_id=tx_id))


@bp.route("/<int:tx_id>/close", methods=["POST"])
@login_required
def close(tx_id):
    tx = db.get_or_404(Transaction, tx_id)
    try:
        close_transaction(tx)
    except LedgerError as e:
        flash(str(e), "warning")
    return redirect(url_for("transactions.detail", tx_id=tx_id))


@bp.route("/<int:tx_id>/reopen", methods=["POST"])
@login_required
def reopen(tx_id):
    tx = db.get_or_404(Transaction, tx_id)
    try:
        reopen_transaction(tx)
    except LedgerError as e:
        flash(str(e), "warning")
    return redirect(url_for("transactions.detail", tx_id=tx_id))
