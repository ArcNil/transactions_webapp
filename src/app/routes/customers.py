from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.customer import Customer
from app.forms.customer import CustomerForm
from app.utils.monitor import record_action

bp = Blueprint("customers", __name__, url_prefix="/customers")


@bp.route("/")
@login_required
def index():
    customers = Customer.query.order_by(Customer.name).all()
    form = CustomerForm()
    return render_template("customers/index.html", customers=customers, form=form)


@bp.route("/add", methods=["POST"])
@login_required
def add():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(name=form.name.data)
        db.session.add(customer)
        db.session.commit()
        record_action(current_user.id, current_user.username, "customer.added", customer.name)
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
        customer.name = form.name.data
        db.session.commit()
        record_action(current_user.id, current_user.username, "customer.edited", customer.name)
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
    db.session.delete(customer)
    db.session.commit()
    record_action(current_user.id, current_user.username, "customer.deleted", customer.name)
    flash(f'Customer "{customer.name}" removed.', "success")
    return redirect(url_for("customers.index"))
