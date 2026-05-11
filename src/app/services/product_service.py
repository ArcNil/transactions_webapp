from decimal import Decimal, InvalidOperation

from app import db
from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient
from app.utils.monitor import record_action


class ProductError(ValueError):
    """Raised when a product operation cannot be completed."""


def upsert_ingredient(
    product,
    stock_item_id: int | str,
    qty_str: str,
    user_id: int,
    username: str,
) -> tuple[str, str]:
    """
    Add or update a product ingredient.

    Parses and validates the raw form values, then either inserts a new
    ProductIngredient row or updates the quantity on an existing one.

    Returns a (flash_message, category) tuple on success.
    Raises ProductError for invalid input or a missing stock item.
    """
    try:
        stock_item_id_int = int(stock_item_id)
        qty = Decimal(qty_str)
    except (ValueError, InvalidOperation):
        raise ProductError("Invalid ingredient data.")

    if qty <= 0:
        raise ProductError("Quantity must be greater than 0.")

    stock_item = db.session.get(StockItem, stock_item_id_int)
    if not stock_item:
        raise ProductError("Stock item not found.")

    existing = ProductIngredient.query.filter_by(
        product_id=product.id, stock_item_id=stock_item.id
    ).first()

    if existing:
        existing.quantity = qty
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        record_action(user_id, username, "product.ingredient_updated", product.name)
        return (
            f'Updated "{stock_item.name}" quantity for "{product.name}".',
            "success",
        )

    ingredient = ProductIngredient(
        product_id=product.id,
        stock_item_id=stock_item.id,
        quantity=qty,
    )
    db.session.add(ingredient)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.ingredient_added", product.name)
    return (
        f'Added "{stock_item.name}" as ingredient for "{product.name}".',
        "success",
    )


def add_product(form, user_id: int, username: str) -> Product:
    """Create and persist a new product from a validated ProductForm."""
    product = Product(
        name=form.name.data,
        unit=form.unit.data,
        price=form.price.data,
        is_active=form.is_active.data,
        show_in_pos=form.show_in_pos.data,
        vendor_id=form.vendor_id.data if form.vendor_id.data != 0 else None,
    )
    db.session.add(product)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.added", product.name)
    return product


def edit_product(product: Product, form, user_id: int, username: str) -> Product:
    """Update an existing product from a validated ProductForm."""
    product.name = form.name.data
    product.unit = form.unit.data
    product.price = form.price.data
    product.is_active = form.is_active.data
    product.show_in_pos = form.show_in_pos.data
    product.vendor_id = form.vendor_id.data if form.vendor_id.data != 0 else None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.edited", product.name)
    return product


def deactivate_product(product: Product, user_id: int, username: str) -> None:
    """Soft-delete a product by marking it inactive."""
    product.is_active = False
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.deleted", product.name)


def toggle_pos(product: Product, user_id: int, username: str) -> Product:
    """Toggle the show_in_pos flag for a product."""
    product.show_in_pos = not product.show_in_pos
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.pos_toggled", product.name)
    return product


def delete_ingredient(
    product_id: int,
    ingredient_id: int,
    user_id: int,
    username: str,
) -> tuple[str, str]:
    """
    Remove a ProductIngredient row.

    Returns a (product_name, stock_name) tuple on success.
    Raises ProductError if the ingredient does not belong to the product.
    """
    ingredient = ProductIngredient.query.filter_by(
        id=ingredient_id, product_id=product_id
    ).first()
    if ingredient is None:
        raise ProductError("Ingredient not found.")
    product_name = ingredient.product.name
    stock_name = ingredient.stock_item.name
    db.session.delete(ingredient)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.ingredient_removed", product_name)
    return product_name, stock_name
