import pytest
from decimal import Decimal
from unittest.mock import patch

from app import db
from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient
from app.services.product_service import (
    ProductError,
    upsert_ingredient,
    add_product,
    edit_product,
    deactivate_product,
    toggle_pos,
    delete_ingredient,
)


class MockField:
    def __init__(self, data):
        self.data = data


class MockProductForm:
    def __init__(
        self,
        name="Test Product",
        unit="unit",
        price=Decimal("10.00"),
        is_active=True,
        show_in_pos=True,
        vendor_id=None,
    ):
        self.name = MockField(name)
        self.unit = MockField(unit)
        self.price = MockField(price)
        self.is_active = MockField(is_active)
        self.show_in_pos = MockField(show_in_pos)
        self.vendor_id = MockField(vendor_id)


class TestUpsertIngredient:
    def test_adds_new_ingredient_happy_path(self, app, sample_product, sample_stock_item, db_session):
        msg, category = upsert_ingredient(
            sample_product, sample_stock_item.id, "2.5", user_id=1, username="admin"
        )

        assert category == "success"
        ingredient = ProductIngredient.query.filter_by(
            product_id=sample_product.id, stock_item_id=sample_stock_item.id
        ).first()
        assert ingredient is not None
        assert ingredient.quantity == Decimal("2.5")

    def test_updates_existing_ingredient_quantity(self, app, sample_product, sample_stock_item, db_session):
        ingredient = ProductIngredient(
            product_id=sample_product.id,
            stock_item_id=sample_stock_item.id,
            quantity=Decimal("1.0"),
        )
        db_session.add(ingredient)
        db_session.commit()

        msg, category = upsert_ingredient(
            sample_product, sample_stock_item.id, "3.0", user_id=1, username="admin"
        )

        assert category == "success"
        db_session.refresh(ingredient)
        assert ingredient.quantity == Decimal("3.0")

    def test_raises_on_non_numeric_stock_item_id(self, app, sample_product):
        with pytest.raises(ProductError, match="Invalid ingredient data"):
            upsert_ingredient(sample_product, "abc", "2.0", user_id=1, username="admin")

    def test_raises_on_non_numeric_qty_str(self, app, sample_product, sample_stock_item):
        with pytest.raises(ProductError, match="Invalid ingredient data"):
            upsert_ingredient(
                sample_product, sample_stock_item.id, "not-a-number", user_id=1, username="admin"
            )

    def test_raises_when_qty_is_zero(self, app, sample_product, sample_stock_item):
        with pytest.raises(ProductError, match="Quantity must be greater than 0"):
            upsert_ingredient(sample_product, sample_stock_item.id, "0", user_id=1, username="admin")

    def test_raises_when_qty_is_negative(self, app, sample_product, sample_stock_item):
        with pytest.raises(ProductError, match="Quantity must be greater than 0"):
            upsert_ingredient(sample_product, sample_stock_item.id, "-1", user_id=1, username="admin")

    def test_raises_when_stock_item_not_found(self, app, sample_product):
        with pytest.raises(ProductError, match="Stock item not found"):
            upsert_ingredient(sample_product, 99999, "1.0", user_id=1, username="admin")

    def test_rollback_called_on_commit_error_update_branch(
        self, app, sample_product, sample_stock_item, db_session
    ):
        ingredient = ProductIngredient(
            product_id=sample_product.id,
            stock_item_id=sample_stock_item.id,
            quantity=Decimal("1.0"),
        )
        db_session.add(ingredient)
        db_session.commit()

        with patch(
            "app.services.product_service.db.session.commit",
            side_effect=RuntimeError("db error"),
        ):
            with patch("app.services.product_service.db.session.rollback") as mock_rollback:
                with pytest.raises(RuntimeError, match="db error"):
                    upsert_ingredient(
                        sample_product, sample_stock_item.id, "3.0", user_id=1, username="admin"
                    )
                mock_rollback.assert_called_once()

    def test_rollback_called_on_commit_error_insert_branch(
        self, app, sample_product, sample_stock_item, db_session
    ):
        with patch(
            "app.services.product_service.db.session.commit",
            side_effect=RuntimeError("db error"),
        ):
            with patch("app.services.product_service.db.session.rollback") as mock_rollback:
                with pytest.raises(RuntimeError, match="db error"):
                    upsert_ingredient(
                        sample_product, sample_stock_item.id, "2.0", user_id=1, username="admin"
                    )
                mock_rollback.assert_called_once()


class TestAddProduct:
    def test_happy_path_creates_and_persists_product(self, app, db_session):
        form = MockProductForm(name="Mineral Water", unit="bottle", price=Decimal("25.00"))
        product = add_product(form, user_id=1, username="admin")

        assert product.id is not None
        assert product.name == "Mineral Water"
        assert product.unit == "bottle"
        assert db_session.get(Product, product.id) is not None

    def test_vendor_id_zero_stored_as_none(self, app, db_session):
        form = MockProductForm(vendor_id=0)
        product = add_product(form, user_id=1, username="admin")

        assert product.vendor_id is None

    def test_rollback_called_on_commit_error(self, app, db_session):
        form = MockProductForm(name="Error Product", unit="unit", price=Decimal("10.00"))

        with patch(
            "app.services.product_service.db.session.commit",
            side_effect=RuntimeError("db error"),
        ):
            with patch("app.services.product_service.db.session.rollback") as mock_rollback:
                with pytest.raises(RuntimeError, match="db error"):
                    add_product(form, user_id=1, username="admin")
                mock_rollback.assert_called_once()


class TestEditProduct:
    def test_happy_path_updates_product_fields(self, app, sample_product, db_session):
        form = MockProductForm(
            name="Updated Name",
            unit="bottle",
            price=Decimal("75.00"),
            is_active=False,
            show_in_pos=False,
        )
        result = edit_product(sample_product, form, user_id=1, username="admin")
        db_session.refresh(sample_product)

        assert result is sample_product
        assert sample_product.name == "Updated Name"
        assert sample_product.unit == "bottle"
        assert sample_product.price == Decimal("75.00")
        assert sample_product.is_active is False
        assert sample_product.show_in_pos is False

    def test_vendor_id_zero_stored_as_none(self, app, sample_product, db_session):
        form = MockProductForm(vendor_id=0)
        edit_product(sample_product, form, user_id=1, username="admin")
        db_session.refresh(sample_product)

        assert sample_product.vendor_id is None

    def test_rollback_called_on_commit_error(self, app, sample_product, db_session):
        form = MockProductForm(name="Updated Name", unit="bottle", price=Decimal("75.00"))

        with patch(
            "app.services.product_service.db.session.commit",
            side_effect=RuntimeError("db error"),
        ):
            with patch("app.services.product_service.db.session.rollback") as mock_rollback:
                with pytest.raises(RuntimeError, match="db error"):
                    edit_product(sample_product, form, user_id=1, username="admin")
                mock_rollback.assert_called_once()


class TestDeactivateProduct:
    def test_sets_is_active_false(self, app, sample_product, db_session):
        assert sample_product.is_active is True

        deactivate_product(sample_product, user_id=1, username="admin")
        db_session.refresh(sample_product)

        assert sample_product.is_active is False

    def test_rollback_called_on_commit_error(self, app, sample_product, db_session):
        with patch(
            "app.services.product_service.db.session.commit",
            side_effect=RuntimeError("db error"),
        ):
            with patch("app.services.product_service.db.session.rollback") as mock_rollback:
                with pytest.raises(RuntimeError, match="db error"):
                    deactivate_product(sample_product, user_id=1, username="admin")
                mock_rollback.assert_called_once()


class TestTogglePos:
    def test_toggles_true_to_false(self, app, db_session):
        product = Product(
            name="Toggle Test",
            unit="unit",
            price=Decimal("10.00"),
            stock=Decimal("5"),
            show_in_pos=True,
        )
        db_session.add(product)
        db_session.commit()

        toggle_pos(product, user_id=1, username="admin")
        db_session.refresh(product)

        assert product.show_in_pos is False

    def test_toggles_false_to_true(self, app, db_session):
        product = Product(
            name="Toggle Test 2",
            unit="unit",
            price=Decimal("10.00"),
            stock=Decimal("5"),
            show_in_pos=False,
        )
        db_session.add(product)
        db_session.commit()

        toggle_pos(product, user_id=1, username="admin")
        db_session.refresh(product)

        assert product.show_in_pos is True

    def test_rollback_called_on_commit_error(self, app, db_session):
        product = Product(
            name="Toggle Error Test",
            unit="unit",
            price=Decimal("10.00"),
            stock=Decimal("5"),
            show_in_pos=True,
        )
        db_session.add(product)
        db_session.commit()

        with patch(
            "app.services.product_service.db.session.commit",
            side_effect=RuntimeError("db error"),
        ):
            with patch("app.services.product_service.db.session.rollback") as mock_rollback:
                with pytest.raises(RuntimeError, match="db error"):
                    toggle_pos(product, user_id=1, username="admin")
                mock_rollback.assert_called_once()


class TestDeleteIngredient:
    def test_happy_path_deletes_ingredient_and_returns_names(
        self, app, sample_product, sample_stock_item, db_session
    ):
        ingredient = ProductIngredient(
            product_id=sample_product.id,
            stock_item_id=sample_stock_item.id,
            quantity=Decimal("1.0"),
        )
        db_session.add(ingredient)
        db_session.commit()
        ingredient_id = ingredient.id

        result = delete_ingredient(sample_product.id, ingredient_id, 1, "testuser")

        assert result == (sample_product.name, sample_stock_item.name)
        assert db_session.get(ProductIngredient, ingredient_id) is None

    def test_raises_product_error_when_ingredient_not_found(self, app):
        with pytest.raises(ProductError, match="Ingredient not found."):
            delete_ingredient(product_id=99999, ingredient_id=99999, user_id=1, username="u")

    def test_rollback_called_on_commit_error(
        self, app, sample_product, sample_stock_item, db_session
    ):
        ingredient = ProductIngredient(
            product_id=sample_product.id,
            stock_item_id=sample_stock_item.id,
            quantity=Decimal("1.0"),
        )
        db_session.add(ingredient)
        db_session.commit()
        ingredient_id = ingredient.id

        with patch(
            "app.services.product_service.db.session.commit",
            side_effect=RuntimeError("db error"),
        ):
            with patch("app.services.product_service.db.session.rollback") as mock_rollback:
                with pytest.raises(RuntimeError, match="db error"):
                    delete_ingredient(sample_product.id, ingredient_id, user_id=1, username="admin")
                mock_rollback.assert_called_once()


