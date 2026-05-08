from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.vendor import Vendor
from app.forms.vendor import VendorForm
from app.services.vendor_service import VendorError, add_vendor, edit_vendor, delete_vendor

bp = Blueprint("vendors", __name__, url_prefix="/vendors")


@bp.route("/")
@login_required
def index():
    vendors = Vendor.query.order_by(Vendor.name).all()
    form = VendorForm()
    return render_template("vendors/index.html", vendors=vendors, form=form)


@bp.route("/add", methods=["POST"])
@login_required
def add():
    form = VendorForm()
    if form.validate_on_submit():
        try:
            vendor = add_vendor(
                form.name.data.strip(),
                current_user.id,
                current_user.username,
            )
            flash(f'Vendor "{vendor.name}" added.', "success")
        except VendorError as e:
            flash(str(e), "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("vendors.index"))


@bp.route("/<int:vendor_id>/edit", methods=["POST"])
@login_required
def edit(vendor_id):
    vendor = db.get_or_404(Vendor, vendor_id)
    form = VendorForm()
    if form.validate_on_submit():
        try:
            edit_vendor(
                vendor,
                form.name.data.strip(),
                current_user.id,
                current_user.username,
            )
            flash(f'Vendor "{vendor.name}" updated.', "success")
        except VendorError as e:
            flash(str(e), "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("vendors.index"))


@bp.route("/<int:vendor_id>/delete", methods=["POST"])
@login_required
def delete(vendor_id):
    vendor = db.get_or_404(Vendor, vendor_id)
    vendor_name = vendor.name
    try:
        delete_vendor(vendor, current_user.id, current_user.username)
        flash(f'Vendor "{vendor_name}" removed.', "success")
    except VendorError as e:
        flash(str(e), "warning")
    return redirect(url_for("vendors.index"))
