from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models.product import Product
from app.models.stock import ProductIngredient
from app.forms.product import ProductForm
from app.services.product_service import (
    get_all_products_with_ingredients,
    get_all_stock_items,
    get_all_vendors,
    upsert_ingredient,
    add_product,
    edit_product,
    deactivate_product,
    toggle_pos as service_toggle_pos,
    delete_ingredient,
    ProductError,
)

bp = Blueprint("products", __name__, url_prefix="/products")


@bp.route("/")
@login_required
def index():
    products = get_all_products_with_ingredients()
    stock_items = get_all_stock_items()
    vendors = get_all_vendors()
    form = ProductForm()

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
        vendors=vendors,
        ingredients_by_product=ingredients_by_product,
        form=form,
    )


@bp.route("/add", methods=["POST"])
@login_required
def add():
    form = ProductForm()
    if form.validate_on_submit():
        raw_vid = request.form.get("vendor_id", "").strip()
        vendor_id = int(raw_vid) if raw_vid.isdigit() and int(raw_vid) > 0 else None
        product = add_product(form, current_user.id, current_user.username, vendor_id=vendor_id)
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
    if form.validate_on_submit():
        raw_vid = request.form.get("vendor_id", "").strip()
        vendor_id = int(raw_vid) if raw_vid.isdigit() and int(raw_vid) > 0 else None
        edit_product(product, form, current_user.id, current_user.username, vendor_id=vendor_id)
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
