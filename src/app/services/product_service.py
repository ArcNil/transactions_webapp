from decimal import Decimal, InvalidOperation
from datetime import timezone

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient, ProductYield
from app.models.vendor import Vendor
from app.utils.monitor import record_action


class ProductError(ValueError):
    """Raised when a product operation cannot be completed."""


def get_all_products_with_ingredients(include_inactive: bool = False) -> list[Product]:
    """Return products, eagerly loading ingredients and their stock items.

    By default only active products are returned. Pass include_inactive=True
    to include deactivated products (used by the 'show deactivated' toggle).
    """
    q = Product.query.options(
        joinedload(Product.ingredients).joinedload(ProductIngredient.stock_item)
    )
    if not include_inactive:
        q = q.filter(Product.is_active.is_(True))
    return q.order_by(Product.name).all()


def count_inactive_products() -> int:
    """Return the number of deactivated products."""
    return Product.query.filter(Product.is_active.is_(False)).count()


def get_products_with_last_used(include_inactive: bool = False) -> list[tuple]:
    """Return (Product, last_used_epoch_int) pairs ordered by most-recently sold first.

    last_used_epoch_int is a Unix timestamp (int seconds) of the most recent sale
    transaction for that product, or 0 if it has never been sold.
    Products never sold sort last, then alphabetically by name.
    """
    # Import here to avoid any circular-import risk.
    from app.models.transaction import Transaction, TransactionItem

    last_used_sub = (
        db.session.query(
            TransactionItem.product_id,
            func.max(Transaction.created_at).label("last_used_at"),
        )
        .join(Transaction, TransactionItem.transaction_id == Transaction.id)
        .filter(
            Transaction.transaction_type == "sale",
            TransactionItem.product_id.isnot(None),
        )
        .group_by(TransactionItem.product_id)
        .subquery()
    )

    q = (
        db.session.query(Product, last_used_sub.c.last_used_at)
        .options(joinedload(Product.ingredients).joinedload(ProductIngredient.stock_item))
        .outerjoin(last_used_sub, Product.id == last_used_sub.c.product_id)
    )

    if not include_inactive:
        q = q.filter(Product.is_active.is_(True))

    q = q.order_by(
        last_used_sub.c.last_used_at.desc().nullslast(),
        Product.name.asc(),
    )

    return [
        (p, int(last_used_at.replace(tzinfo=timezone.utc).timestamp()) if last_used_at else 0)
        for p, last_used_at in q.all()
    ]


def get_all_stock_items() -> list[StockItem]:
    """Return all stock items ordered by name."""
    return StockItem.query.order_by(StockItem.name).all()


def get_all_vendors() -> list[Vendor]:
    """Return all vendors ordered by name."""
    return Vendor.query.order_by(Vendor.name).all()


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


def add_product(
    form, user_id: int, username: str, vendor_id: int | None = None, photo_data: str | None = None
) -> Product:
    """Create and persist a new product from a validated ProductForm."""
    product_type = form.product_type.data
    # Purchase items are raw materials — hide from POS unless explicitly enabled.
    show_in_pos = form.show_in_pos.data if product_type == "sale" else False
    product = Product(
        name=form.name.data,
        product_type=product_type,
        unit=form.unit.data,
        price=form.price.data,
        is_active=form.is_active.data,
        show_in_pos=show_in_pos,
        vendor_id=vendor_id,
        photo_data=photo_data,
    )
    db.session.add(product)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.added", product.name)
    return product


def edit_product(
    product: Product,
    form,
    user_id: int,
    username: str,
    vendor_id: int | None = None,
    photo_data: str | None = None,
    remove_photo: bool = False,
) -> Product:
    """Update an existing product from a validated ProductForm."""
    product_type = form.product_type.data
    product.name = form.name.data
    product.product_type = product_type
    product.unit = form.unit.data
    product.price = form.price.data
    product.is_active = form.is_active.data
    # Purchase items cannot be shown in POS.
    product.show_in_pos = form.show_in_pos.data if product_type == "sale" else False
    product.vendor_id = vendor_id
    if remove_photo:
        product.photo_data = None
    elif photo_data is not None:
        product.photo_data = photo_data
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
    """Toggle the show_in_pos flag for a product.

    Purchase-type products cannot be shown in POS — raises ProductError if attempted.
    """
    if product.product_type == "purchase":
        raise ProductError("Purchase products cannot be shown in POS.")
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


def upsert_yield(
    product,
    stock_item_id: int | str,
    qty_str: str,
    user_id: int,
    username: str,
) -> tuple[str, str]:
    """
    Add or update a product yield mapping.

    A yield defines how much of a raw stock item is added per 1 unit of a
    purchase product when it is restocked. Only valid for purchase-type products.

    Returns a (flash_message, category) tuple on success.
    Raises ProductError for invalid input, wrong product type, or missing stock item.
    """
    if product.product_type != "purchase":
        raise ProductError("Yield mappings are only valid for purchase-type products.")

    try:
        stock_item_id_int = int(stock_item_id)
        qty = Decimal(qty_str)
    except (ValueError, InvalidOperation):
        raise ProductError("Invalid yield data.")

    if qty <= 0:
        raise ProductError("Quantity must be greater than 0.")

    stock_item = db.session.get(StockItem, stock_item_id_int)
    if not stock_item:
        raise ProductError("Stock item not found.")

    existing = ProductYield.query.filter_by(
        product_id=product.id, stock_item_id=stock_item.id
    ).first()

    if existing:
        existing.quantity = qty
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        record_action(user_id, username, "product.yield_updated", product.name)
        return (
            f'Updated yield: "{stock_item.name}" for "{product.name}".',
            "success",
        )

    product_yield = ProductYield(
        product_id=product.id,
        stock_item_id=stock_item.id,
        quantity=qty,
    )
    db.session.add(product_yield)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.yield_added", product.name)
    return (
        f'Added yield: 1 {product.unit} of "{product.name}" adds {qty} {stock_item.unit}(s) of "{stock_item.name}".',
        "success",
    )


def delete_yield(
    product_id: int,
    yield_id: int,
    user_id: int,
    username: str,
) -> tuple[str, str]:
    """
    Remove a ProductYield row.

    Returns a (product_name, stock_name) tuple on success.
    Raises ProductError if the yield does not belong to the product.
    """
    product_yield = ProductYield.query.filter_by(
        id=yield_id, product_id=product_id
    ).first()
    if product_yield is None:
        raise ProductError("Yield mapping not found.")
    product_name = product_yield.product.name
    stock_name = product_yield.stock_item.name
    db.session.delete(product_yield)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "product.yield_removed", product_name)
    return product_name, stock_name
