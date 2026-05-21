from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
import base64
from app import db
from app.models.product import Product
from app.models.stock import ProductIngredient
from app.forms.product import ProductForm
from app.services.product_service import (
    get_products_with_last_used,
    count_inactive_products,
    get_all_stock_items,
    get_all_vendors,
    upsert_ingredient,
    upsert_yield,
    add_product,
    edit_product,
    deactivate_product,
    toggle_pos as service_toggle_pos,
    delete_ingredient,
    delete_yield,
    ProductError,
)

bp = Blueprint("products", __name__, url_prefix="/products")

_MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB

def _get_image_mime(stream) -> str | None:
    """Return MIME type from magic bytes, or None if not a recognised image format."""
    header = stream.read(12)
    stream.seek(0)
    if header[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if header[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _process_photo(file_storage) -> tuple[str | None, str | None]:
    """Validate and encode an uploaded photo.

    Returns (data_uri, None) on success, or (None, error_message) on failure.
    """
    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size > _MAX_PHOTO_BYTES:
        return None, "Photo must be under 2 MB."
    mime = _get_image_mime(stream)
    if mime is None:
        return None, "Unsupported image format. Use JPEG, PNG, GIF, or WebP."
    raw = stream.read()
    data_uri = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    return data_uri, None


@bp.route("/")
@login_required
def index():
    show_inactive = request.args.get("show_inactive", "0") == "1"
    rows = get_products_with_last_used(include_inactive=show_inactive)
    products = [p for p, _ in rows]
    last_used_by_product = {p.id: ts for p, ts in rows}
    inactive_count = count_inactive_products()
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

    # Pre-serialize yields per purchase product for safe JS consumption
    yields_by_product = {
        p.id: [
            {
                "id": y.id,
                "stock_item_name": y.stock_item.name,
                "stock_item_unit": y.stock_item.unit,
                "quantity": str(y.quantity),
            }
            for y in p.yields
        ]
        for p in products
        if p.product_type == "purchase"
    }

    return render_template(
        "products/index.html",
        products=products,
        last_used_by_product=last_used_by_product,
        stock_items=stock_items,
        vendors=vendors,
        ingredients_by_product=ingredients_by_product,
        yields_by_product=yields_by_product,
        form=form,
        show_inactive=show_inactive,
        inactive_count=inactive_count,
    )


@bp.route("/add", methods=["POST"])
@login_required
def add():
    form = ProductForm()
    if form.validate_on_submit():
        raw_vid = request.form.get("vendor_id", "").strip()
        vendor_id = int(raw_vid) if raw_vid.isdigit() and int(raw_vid) > 0 else None
        photo_data = None
        if form.photo.data:
            photo_data, err = _process_photo(form.photo.data)
            if err:
                flash(err, "danger")
                return redirect(url_for("products.index"))
        product = add_product(form, current_user.id, current_user.username, vendor_id=vendor_id, photo_data=photo_data)
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
        photo_data = None
        remove_photo = form.remove_photo.data
        if not remove_photo and form.photo.data:
            photo_data, err = _process_photo(form.photo.data)
            if err:
                flash(err, "danger")
                return redirect(url_for("products.index"))
        edit_product(
            product, form, current_user.id, current_user.username,
            vendor_id=vendor_id, photo_data=photo_data, remove_photo=remove_photo,
        )
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
    try:
        service_toggle_pos(product, current_user.id, current_user.username)
        state = "shown in" if product.show_in_pos else "hidden from"
        flash(f'"{product.name}" is now {state} POS.', "success")
    except ProductError as e:
        flash(str(e), "danger")
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


@bp.route("/<int:product_id>/yields/add", methods=["POST"])
@login_required
def yield_add(product_id):
    product = db.get_or_404(Product, product_id)
    try:
        msg, category = upsert_yield(
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


@bp.route("/<int:product_id>/yields/<int:yield_id>/delete", methods=["POST"])
@login_required
def yield_delete(product_id, yield_id):
    try:
        product_name, stock_name = delete_yield(
            product_id, yield_id, current_user.id, current_user.username
        )
    except ProductError:
        abort(404)
    flash(f'Removed "{stock_name}" yield from "{product_name}".', "success")
    return redirect(url_for("products.index"))
