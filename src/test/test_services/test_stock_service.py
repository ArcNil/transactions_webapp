import pytest
from decimal import Decimal
from unittest.mock import patch

from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient
from app.services.stock_service import StockError, delete_stock_item


class TestDeleteStockItem:
    def test_happy_path_deletes_item_from_db(self, app, sample_stock_item, db_session):
        item_id = sample_stock_item.id
        delete_stock_item(sample_stock_item, user_id=1, username="admin")

        assert db_session.get(StockItem, item_id) is None

    def test_raises_stock_error_when_item_has_ingredients(
        self, app, sample_product, sample_stock_item, db_session
    ):
        ingredient = ProductIngredient(
            product_id=sample_product.id,
            stock_item_id=sample_stock_item.id,
            quantity=Decimal("1.0"),
        )
        db_session.add(ingredient)
        db_session.commit()

        with pytest.raises(StockError, match="ingredient"):
            delete_stock_item(sample_stock_item, user_id=1, username="admin")

    def test_rollback_called_on_commit_error(self, app, sample_stock_item, db_session):
        with patch(
            "app.services.stock_service.db.session.commit",
            side_effect=RuntimeError("db error"),
        ):
            with patch("app.services.stock_service.db.session.rollback") as mock_rollback:
                with pytest.raises(RuntimeError, match="db error"):
                    delete_stock_item(sample_stock_item, user_id=1, username="admin")
                mock_rollback.assert_called_once()
