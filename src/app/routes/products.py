from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app import db
from app.models.product import Product
from app.models.vendor import Vendor
from app.models.stock import StockItem, ProductIngredient
from app.forms.product import ProductForm
from app.services.product_service import (
    upsert_ingredient,
    add_product,
    edit_product,
    deactivate_product,
    toggle_pos as service_toggle_pos,
    delete_ingredient,
    ProductError,
)

bp = Blueprint("products", __name__, url_prefix="/products")


def _vendor_choices():
    """Return SelectField choices: [(0, '— None —'), (id, name), ...]"""
    vendors = Vendor.query.order_by(Vendor.name).all()
    return [(0, "— None —")] + [(v.id, v.name) for v in vendors]


@bp.route("/")
@login_required
def index():
    products = (
        Product.query
        .options(joinedload(Product.ingredients).joinedload(ProductIngredient.stock_item))
        .order_by(Product.name)
        .all()
    )
    stock_items = StockItem.query.order_by(StockItem.name).all()
    form = ProductForm()
    form.vendor_id.choices = _vendor_choices()

    # Pre-serialize ingredients per product for safe JS consumption
    ingredients_by_product = {
        p.id: [
            {
                "id": ing.id,
                "stock_item_name": ing.stock_item.name,
                "stock_item_unit": ing.stock_item.unit,
                "quantity": str(ing.quantity),
            }
            for ing in p.ingredients
        ]
        for p in products
    }

    return render_template(
        "products/index.html",
        products=products,
        stock_items=stock_items,
        ingredients_by_product=ingredients_by_product,
        form=form,
    )


@bp.route("/add", methods=["POST"])
@login_required
def add():
    form = ProductForm()
    form.vendor_id.choices = _vendor_choices()
    if form.validate_on_submit():
        product = add_product(form, current_user.id, current_user.username)
        flash(f'Product "{product.name}" added.', "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("products.index"))


@bp.route("/<int:product_id>/edit", methods=["POST"])
@login_required
def edit(product_id):
    product = db.get_or_404(Product, product_id)
    form = ProductForm()
    form.vendor_id.choices = _vendor_choices()
    if form.validate_on_submit():
        edit_product(product, form, current_user.id, current_user.username)
        flash(f'Product "{product.name}" updated.', "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    return redirect(url_for("products.index"))


@bp.route("/<int:product_id>/delete", methods=["POST"])
@login_required
def delete(product_id):
    product = db.get_or_404(Product, product_id)
    product_name = product.name
    deactivate_product(product, current_user.id, current_user.username)
    flash(f'Product "{product_name}" deactivated.', "success")
    return redirect(url_for("products.index"))


@bp.route("/<int:product_id>/toggle_pos", methods=["POST"])
@login_required
def toggle_pos(product_id):
    product = db.get_or_404(Product, product_id)
    service_toggle_pos(product, current_user.id, current_user.username)
    state = "shown in" if product.show_in_pos else "hidden from"
    flash(f'"{product.name}" is now {state} POS.', "success")
    return redirect(url_for("products.index"))


@bp.route("/<int:product_id>/ingredients/add", methods=["POST"])
@login_required
def ingredient_add(product_id):
    product = db.get_or_404(Product, product_id)
    try:
        msg, category = upsert_ingredient(
            product,
            request.form.get("stock_item_id", "0"),
            request.form.get("quantity", "0"),
            current_user.id,
            current_user.username,
        )
        flash(msg, category)
    except ProductError as e:
        flash(str(e), "danger")
    return redirect(url_for("products.index"))


@bp.route("/<int:product_id>/ingredients/<int:ingredient_id>/delete", methods=["POST"])
@login_required
def ingredient_delete(product_id, ingredient_id):
    try:
        product_name, stock_name = delete_ingredient(
            product_id, ingredient_id, current_user.id, current_user.username
        )
    except ProductError:
        abort(404)
    flash(f'Removed "{stock_name}" from "{product_name}" ingredients.', "success")
    return redirect(url_for("products.index"))
