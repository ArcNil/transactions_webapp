import json
from decimal import Decimal, InvalidOperation

from app import db
from app.models.product import Product
from app.models.transaction import Transaction, TransactionItem
from app.models.vendor import Vendor


class TransactionError(ValueError):
    """Raised when cart or item data is invalid."""


def _check_ingredient_stock(product: Product, quantity: Decimal) -> None:
    """Raise TransactionError if raw stock is insufficient for the requested quantity."""
    for ing in product.ingredients:
        needed = ing.quantity * quantity
        if ing.stock_item.quantity < needed:
            raise TransactionError(
                f'Not enough "{ing.stock_item.name}" to make {quantity} {product.unit}(s) of '
                f'"{product.name}". Need {needed} {ing.stock_item.unit}(s), '
                f'have {ing.stock_item.quantity}.'
            )


def _deduct_ingredient_stock(product: Product, quantity: Decimal) -> None:
    """Decrement each raw stock item consumed by selling `quantity` units of product."""
    for ing in product.ingredients:
        ing.stock_item.quantity -= ing.quantity * quantity


def _adjust_product_stock(product: Product, delta: Decimal) -> None:
    """
    Apply a stock delta to a product.

    Positive delta deducts stock (more sold); negative delta restores it (fewer sold).
    Works for both ingredient-based and direct-stock products.
    """
    if product.ingredients:
        for ing in product.ingredients:
            ing.stock_item.quantity -= ing.quantity * delta
    else:
        product.stock -= delta


def _parse_items(items_data: list, check_stock: bool = False) -> tuple[list, Decimal]:
    """
    Validate and resolve each entry in the cart.

    Returns a list of resolved line-item dicts and the computed total.
    Raises TransactionError on any invalid entry.
    When check_stock is True, raises TransactionError if a catalog product
    has insufficient stock (raw-ingredient or direct stock depending on product type).
    """
    line_items = []
    total = Decimal("0")

    for entry in items_data:
        try:
            quantity = Decimal(str(entry["quantity"]))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            raise TransactionError("Invalid item data.")

        if quantity <= 0:
            raise TransactionError("Quantity must be greater than zero.")

        if entry.get("product_id") is None:
            # Ad-hoc / custom item — not stock-tracked
            custom_name = str(entry.get("name", "")).strip()[:128]
            custom_unit = str(entry.get("unit", "")).strip()[:64]
            try:
                custom_price = Decimal(str(entry["price"]))
            except (KeyError, ValueError, TypeError, InvalidOperation):
                raise TransactionError("Invalid custom item price.")
            if not custom_name or not custom_unit or custom_price <= 0:
                raise TransactionError("Custom item requires a name, unit, and price > 0.")
            subtotal = custom_price * quantity
            total += subtotal
            line_items.append({
                "product": None,
                "name": custom_name,
                "unit": custom_unit,
                "price": custom_price,
                "quantity": quantity,
                "subtotal": subtotal,
            })
        else:
            try:
                product_id = int(entry["product_id"])
            except (ValueError, TypeError):
                raise TransactionError("Invalid item data.")
            product = db.session.get(Product, product_id)
            if not product:
                raise TransactionError(f"Product #{product_id} not found.")
            if check_stock:
                if product.ingredients:
                    _check_ingredient_stock(product, quantity)
                elif product.stock < quantity:
                    raise TransactionError(
                        f'"{product.name}" only has {product.stock} {product.unit}(s) in stock.'
                    )
            subtotal = product.price * quantity
            total += subtotal
            line_items.append({
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal,
            })

    return line_items, total


def create_transaction(
    items_raw: str,
    customer_id: str | None,
) -> Transaction:
    """
    Parse the cart payload and persist a new Transaction with its items.

    Payment entries are recorded separately via ledger_service.
    Raises TransactionError if the payload is invalid.
    """
    try:
        items_data = json.loads(items_raw)
    except (ValueError, TypeError):
        raise TransactionError("Invalid cart data.")

    if not items_data:
        raise TransactionError("Cart is empty.")

    line_items, total = _parse_items(items_data, check_stock=True)

    tx = Transaction(
        transaction_type="sale",
        customer_id=int(customer_id) if customer_id else None,
        total_amount=total,
    )
    db.session.add(tx)
    db.session.flush()

    for li in line_items:
        p = li["product"]
        if p is None:
            item = TransactionItem(
                transaction_id=tx.id,
                product_id=None,
                product_name_snapshot=li["name"],
                unit_snapshot=li["unit"],
                unit_price_snapshot=li["price"],
                quantity=li["quantity"],
                subtotal=li["subtotal"],
            )
        else:
            if p.ingredients:
                # Consume raw stock ingredients
                _deduct_ingredient_stock(p, li["quantity"])
            else:
                # Decrement direct product stock
                p.stock -= li["quantity"]
            item = TransactionItem(
                transaction_id=tx.id,
                product_id=p.id,
                product_name_snapshot=p.name,
                unit_snapshot=p.unit,
                unit_price_snapshot=p.price,
                quantity=li["quantity"],
                subtotal=li["subtotal"],
            )
        db.session.add(item)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return tx


def update_transaction(
    tx: Transaction,
    items_raw: str,
    customer_id: str | None,
) -> Transaction:
    """
    Reconcile items and update an existing Transaction.

    - Existing items whose quantity changed are updated in place (price snapshot preserved).
    - Items absent from the submission are deleted.
    - New items are snapshotted from the current product price.

    Payment entries are managed separately via ledger_service.
    Raises TransactionError if the payload is invalid.
    """
    try:
        items_data = json.loads(items_raw)
    except (ValueError, TypeError):
        raise TransactionError("Invalid item data.")

    if not items_data:
        raise TransactionError("A transaction must have at least one item.")

    existing = {item.id: item for item in tx.items}
    submitted_item_ids = set()
    total = Decimal("0")
    valid_item_count = 0

    # Track net stock delta per product for sale transactions.
    # Positive = sold more (deduct), negative = sold less (restore).
    # {product_id: [product_obj, net_delta]}
    stock_deltas: dict[int, list] = {}

    def _accum_delta(product: Product, delta: Decimal) -> None:
        pid = product.id
        if pid not in stock_deltas:
            stock_deltas[pid] = [product, Decimal("0")]
        stock_deltas[pid][1] += delta

    for entry in items_data:
        try:
            quantity = Decimal(str(entry["quantity"]))
            if quantity <= 0:
                continue
        except (KeyError, ValueError, InvalidOperation):
            raise TransactionError("Invalid quantity.")

        item_id = entry.get("item_id")

        if item_id and int(item_id) in existing:
            item = existing[int(item_id)]
            old_qty = item.quantity
            item.quantity = quantity
            item.subtotal = item.unit_price_snapshot * quantity
            submitted_item_ids.add(item.id)
            total += item.subtotal
            valid_item_count += 1
            # Accumulate delta: positive if qty increased, negative if decreased
            if tx.transaction_type == "sale" and item.product_id and item.product:
                _accum_delta(item.product, quantity - old_qty)
        else:
            if entry.get("product_id") is None:
                # Ad-hoc / custom item
                custom_name = str(entry.get("name", "")).strip()[:128]
                custom_unit = str(entry.get("unit", "")).strip()[:64]
                try:
                    custom_price = Decimal(str(entry["price"]))
                except (KeyError, ValueError, TypeError, InvalidOperation):
                    raise TransactionError("Invalid custom item price.")
                if not custom_name or not custom_unit or custom_price <= 0:
                    raise TransactionError("Custom item requires a name, unit, and price > 0.")
                subtotal = custom_price * quantity
                new_item = TransactionItem(
                    transaction_id=tx.id,
                    product_id=None,
                    product_name_snapshot=custom_name,
                    unit_snapshot=custom_unit,
                    unit_price_snapshot=custom_price,
                    quantity=quantity,
                    subtotal=subtotal,
                )
                db.session.add(new_item)
                total += subtotal
                valid_item_count += 1
            else:
                try:
                    product_id = int(entry["product_id"])
                except (KeyError, ValueError, TypeError):
                    raise TransactionError("Invalid product.")
                product = db.session.get(Product, product_id)
                if not product:
                    raise TransactionError(f"Product #{product_id} not found.")
                subtotal = product.price * quantity
                new_item = TransactionItem(
                    transaction_id=tx.id,
                    product_id=product.id,
                    product_name_snapshot=product.name,
                    unit_snapshot=product.unit,
                    unit_price_snapshot=product.price,
                    quantity=quantity,
                    subtotal=subtotal,
                )
                db.session.add(new_item)
                total += subtotal
                valid_item_count += 1
                # New item: full deduction
                if tx.transaction_type == "sale":
                    _accum_delta(product, quantity)

    if valid_item_count == 0:
        raise TransactionError("All submitted items have zero or negative quantity.")

    for item_id, item in existing.items():
        if item_id not in submitted_item_ids:
            db.session.delete(item)
            # Deleted item: restore its stock
            if tx.transaction_type == "sale" and item.product_id and item.product:
                _accum_delta(item.product, -item.quantity)

    # Apply stock adjustments for sale transactions.
    # Restores (negative deltas) are applied first so freed stock is available for deductions.
    if tx.transaction_type == "sale":
        for product, delta in stock_deltas.values():
            if delta < 0:
                _adjust_product_stock(product, delta)

        for product, delta in stock_deltas.values():
            if delta > 0:
                if product.ingredients:
                    _check_ingredient_stock(product, delta)
                elif product.stock < delta:
                    raise TransactionError(
                        f'"{product.name}" only has {product.stock} {product.unit}(s) in stock.'
                    )
                _adjust_product_stock(product, delta)

    tx.total_amount = total
    tx.customer_id = int(customer_id) if customer_id else None

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return tx


def create_restock(
    items_raw: str,
    vendor_id: str,
) -> Transaction:
    """
    Record a restock transaction (admin buying from a vendor).

    Increments stock for each catalog product in the cart.
    Payment entries are recorded separately via ledger_service.
    Raises TransactionError if the payload is invalid.
    """

    try:
        vid = int(vendor_id)
    except (ValueError, TypeError):
        raise TransactionError("A vendor must be selected.")

    vendor = db.session.get(Vendor, vid)
    if not vendor:
        raise TransactionError("Vendor not found.")

    try:
        items_data = json.loads(items_raw)
    except (ValueError, TypeError):
        raise TransactionError("Invalid cart data.")

    if not items_data:
        raise TransactionError("Cart is empty.")

    # Restock items must all be catalog products (no ad-hoc)
    for entry in items_data:
        if entry.get("product_id") is None:
            raise TransactionError("Restock items must be catalog products.")

    # Parse items with submitted cost prices (not retail prices)
    line_items = []
    total = Decimal("0")

    for entry in items_data:
        try:
            product_id = int(entry["product_id"])
            quantity = Decimal(str(entry["quantity"]))
            unit_price = Decimal(str(entry["unit_price"]))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            raise TransactionError("Invalid item data.")

        if quantity <= 0:
            raise TransactionError("Quantity must be greater than zero.")
        if unit_price < 0:
            raise TransactionError("Unit price must be >= 0.")

        product = db.session.get(Product, product_id)
        if not product:
            raise TransactionError(f"Product #{product_id} not found.")

        subtotal = unit_price * quantity
        total += subtotal
        line_items.append({
            "product": product,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })

    tx = Transaction(
        transaction_type="restock",
        vendor_id=vid,
        total_amount=total,
    )
    db.session.add(tx)
    db.session.flush()

    for li in line_items:
        p = li["product"]
        # Increment stock
        p.stock += li["quantity"]
        item = TransactionItem(
            transaction_id=tx.id,
            product_id=p.id,
            product_name_snapshot=p.name,
            unit_snapshot=p.unit,
            unit_price_snapshot=li["unit_price"],
            quantity=li["quantity"],
            subtotal=li["subtotal"],
        )
        db.session.add(item)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return tx


def create_stock_restock(
    items_raw: str,
    vendor_id: str,
) -> Transaction:
    """
    Record a stock_restock transaction (admin buying raw stock from a vendor).

    Each line item references a StockItem; quantity is added to stock_item.quantity.
    Payment entries are recorded separately via ledger_service.
    Raises TransactionError if the payload is invalid.
    """
    from app.models.stock import StockItem

    try:
        vid = int(vendor_id)
    except (ValueError, TypeError):
        raise TransactionError("A vendor must be selected.")

    vendor = db.session.get(Vendor, vid)
    if not vendor:
        raise TransactionError("Vendor not found.")

    try:
        items_data = json.loads(items_raw)
    except (ValueError, TypeError):
        raise TransactionError("Invalid cart data.")

    if not items_data:
        raise TransactionError("Cart is empty.")

    line_items = []
    total = Decimal("0")

    for entry in items_data:
        try:
            stock_item_id = int(entry["stock_item_id"])
            quantity = Decimal(str(entry["quantity"]))
            unit_price = Decimal(str(entry["unit_price"]))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            raise TransactionError("Invalid item data.")

        if quantity <= 0 or unit_price < 0:
            raise TransactionError("Quantity must be > 0 and price must be >= 0.")

        stock_item = db.session.get(StockItem, stock_item_id)
        if not stock_item:
            raise TransactionError(f"Stock item #{stock_item_id} not found.")

        subtotal = unit_price * quantity
        total += subtotal
        line_items.append({
            "stock_item": stock_item,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })

    tx = Transaction(
        transaction_type="stock_restock",
        vendor_id=vid,
        total_amount=total,
    )
    db.session.add(tx)
    db.session.flush()

    for li in line_items:
        si = li["stock_item"]
        # Increment raw stock quantity
        si.quantity += li["quantity"]
        item = TransactionItem(
            transaction_id=tx.id,
            product_id=None,
            stock_item_id=si.id,
            product_name_snapshot=si.name,
            unit_snapshot=si.unit,
            unit_price_snapshot=li["unit_price"],
            quantity=li["quantity"],
            subtotal=li["subtotal"],
        )
        db.session.add(item)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return tx


def create_product_restock(
    items_raw: str,
    vendor_id: str,
) -> Transaction:
    """
    Record a stock_restock transaction where each line item is a Product
    (with ingredients).  Restocking N units of a product adds
    ingredient.quantity * N to each linked StockItem.

    Payload format: [{product_id, quantity, unit_price}, ...]
    Payment entries are recorded separately via ledger_service.
    Raises TransactionError if the payload is invalid.
    """
    try:
        vid = int(vendor_id)
    except (ValueError, TypeError):
        raise TransactionError("A vendor must be selected.")

    vendor = db.session.get(Vendor, vid)
    if not vendor:
        raise TransactionError("Vendor not found.")

    try:
        items_data = json.loads(items_raw)
    except (ValueError, TypeError):
        raise TransactionError("Invalid cart data.")

    if not items_data:
        raise TransactionError("Cart is empty.")

    line_items = []
    total = Decimal("0")

    for entry in items_data:
        try:
            product_id = int(entry["product_id"])
            quantity = Decimal(str(entry["quantity"]))
            unit_price = Decimal(str(entry["unit_price"]))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            raise TransactionError("Invalid item data.")

        if quantity <= 0 or unit_price < 0:
            raise TransactionError("Quantity must be > 0 and price must be >= 0.")

        product = db.session.get(Product, product_id)
        if not product:
            raise TransactionError(f"Product #{product_id} not found.")
        # Products without ingredients are valid (e.g. services/fees); they record
        # the transaction but do not fan out to raw stock.

        subtotal = unit_price * quantity
        total += subtotal
        line_items.append({
            "product": product,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })

    try:
        tx = Transaction(
            transaction_type="product_restock",
            vendor_id=vid,
            total_amount=total,
        )
        db.session.add(tx)
        db.session.flush()

        for li in line_items:
            p = li["product"]
            qty = li["quantity"]
            # Increment each linked raw stock item proportionally
            for ing in p.ingredients:
                ing.stock_item.quantity += ing.quantity * qty

            item = TransactionItem(
                transaction_id=tx.id,
                product_id=p.id,
                stock_item_id=None,
                product_name_snapshot=p.name,
                unit_snapshot=p.unit,
                unit_price_snapshot=li["unit_price"],
                quantity=qty,
                subtotal=li["subtotal"],
            )
            db.session.add(item)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return tx
