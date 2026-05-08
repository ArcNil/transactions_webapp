from app import db
from app.models.stock import StockItem
from app.utils.monitor import record_action


class StockError(ValueError):
    """Raised when a stock operation cannot be completed."""


def delete_stock_item(item: StockItem, user_id: int, username: str) -> None:
    """
    Delete a stock item.

    Raises StockError if the item is used as an ingredient in any product.
    """
    if item.ingredients:
        raise StockError(
            f'Cannot delete "{item.name}" — it is used as an ingredient '
            "in one or more products."
        )
    item_name = item.name
    db.session.delete(item)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "stock_item.deleted", item_name)
