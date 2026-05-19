from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.customer import Customer
from app.forms.customer import CustomerForm
from app.services.customer_service import (
    get_all_customers,
    add_customer,
    edit_customer,
    delete_customer,
    CustomerError,
)

bp = Blueprint("customers", __name__, url_prefix="/customers")


@bp.route("/")
@login_required
def index():
    customers = get_all_customers()
    form = CustomerForm()
    return render_template("customers/index.html", customers=customers, form=form)


@bp.route("/add", methods=["POST"])
@login_required
def add():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = add_customer(form, current_user.id, current_user.username)
        flash(f'Customer "{customer.name}" added.', "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("customers.index"))


@bp.route("/<int:customer_id>/edit", methods=["POST"])
@login_required
def edit(customer_id):
    customer = db.get_or_404(Customer, customer_id)
    form = CustomerForm()
    if form.validate_on_submit():
        edit_customer(customer, form, current_user.id, current_user.username)
        flash(f'Customer "{customer.name}" updated.', "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("customers.index"))


@bp.route("/<int:customer_id>/delete", methods=["POST"])
@login_required
def delete(customer_id):
    customer = db.get_or_404(Customer, customer_id)
    customer_name = customer.name
    try:
        delete_customer(customer, current_user.id, current_user.username)
        flash(f'Customer "{customer_name}" removed.', "success")
    except CustomerError as e:
        flash(str(e), "danger")
    return redirect(url_for("customers.index"))

