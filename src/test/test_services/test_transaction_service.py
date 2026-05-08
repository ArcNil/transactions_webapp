import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from app import db
from app.models.product import Product
from app.models.transaction import Transaction, TransactionItem
from app.services.transaction_service import (
    TransactionError,
    create_restock,
    create_stock_restock,
    create_transaction,
    update_transaction,
)


class TestCreateTransaction:
    def test_creates_transaction_with_catalog_product(self, app, sample_product, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": 2}])
        tx = create_transaction(items, None, "full", None)

        assert tx.id is not None
        assert len(tx.items) == 1
        assert tx.items[0].product_id == sample_product.id
        assert tx.items[0].quantity == Decimal("2")

    def test_creates_transaction_with_custom_item(self, app, db_session):
        items = json.dumps([
            {
                "product_id": None,
                "name": "Custom Water",
                "unit": "bottle",
                "price": "25.00",
                "quantity": 3,
            }
        ])
        tx = create_transaction(items, None, "full", None)

        assert tx.id is not None
        assert len(tx.items) == 1
        item = tx.items[0]
        assert item.product_id is None
        assert item.product_name_snapshot == "Custom Water"
        assert item.unit_snapshot == "bottle"

    def test_sets_amount_paid_to_total_when_full(self, app, sample_product, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": 2}])
        tx = create_transaction(items, None, "full", "0")

        expected_total = sample_product.price * 2
        assert tx.amount_paid == expected_total
        assert tx.total_amount == expected_total

    def test_sets_amount_paid_to_zero_when_unpaid(self, app, sample_product, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": 2}])
        tx = create_transaction(items, None, "unpaid", None)

        assert tx.amount_paid == Decimal("0")

    def test_uses_provided_amount_paid_when_partial(self, app, sample_product, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": 2}])
        tx = create_transaction(items, None, "partial", "50.00")

        assert tx.amount_paid == Decimal("50.00")
        assert tx.payment_status == "partial"

    def test_raises_for_invalid_payment_status(self, app, sample_product, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": 1}])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "invalid_status", None)

    def test_raises_for_malformed_json(self, app, db_session):
        with pytest.raises(TransactionError):
            create_transaction("not-valid-json{{", None, "full", None)

    def test_raises_for_empty_cart(self, app, db_session):
        with pytest.raises(TransactionError):
            create_transaction(json.dumps([]), None, "full", None)

    def test_raises_for_nonexistent_product_id(self, app, db_session):
        items = json.dumps([{"product_id": 99999, "quantity": 1}])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_raises_for_custom_item_with_no_name(self, app, db_session):
        items = json.dumps([
            {"product_id": None, "name": "", "unit": "bottle", "price": "25.00", "quantity": 1}
        ])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_raises_for_custom_item_with_zero_price(self, app, db_session):
        items = json.dumps([
            {"product_id": None, "name": "Custom Water", "unit": "bottle", "price": "0", "quantity": 1}
        ])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_raises_for_invalid_quantity_value(self, app, db_session):
        items = json.dumps([
            {"product_id": None, "name": "Test", "unit": "unit", "price": "10.00", "quantity": "not-a-number"}
        ])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_customer_id_stored_on_transaction(self, app, sample_product, sample_customer, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": 1}])
        tx = create_transaction(items, str(sample_customer.id), "full", None)

        assert tx.customer_id == sample_customer.id

    def test_total_is_sum_of_all_item_subtotals_for_multiple_items(self, app, db_session):
        product_a = Product(name="Product A", unit="unit", price="30.00", stock=Decimal("100"))
        product_b = Product(name="Product B", unit="unit", price="20.00", stock=Decimal("100"))
        db_session.add_all([product_a, product_b])
        db_session.commit()

        items = json.dumps([
            {"product_id": product_a.id, "quantity": 2},
            {"product_id": product_b.id, "quantity": 3},
        ])
        tx = create_transaction(items, None, "full", None)

        assert tx.total_amount == Decimal("120.00")
        assert len(tx.items) == 2

    def test_raises_for_custom_item_missing_unit(self, app, db_session):
        items = json.dumps([
            {"product_id": None, "name": "Water", "unit": "", "price": "25.00", "quantity": 1}
        ])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_raises_for_custom_item_with_negative_price(self, app, db_session):
        items = json.dumps([
            {"product_id": None, "name": "Water", "unit": "bottle", "price": "-5.00", "quantity": 1}
        ])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_create_transaction_raises_for_zero_quantity(self, app, sample_product, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": 0}])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_create_transaction_raises_for_negative_quantity(self, app, sample_product, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": -1}])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_commit_failure_rolls_back_and_propagates(self, app, sample_product, db_session):
        items = json.dumps([{"product_id": sample_product.id, "quantity": 1}])
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                create_transaction(items, None, "full", None)
        mock_rollback.assert_called_once()

    def test_raises_for_invalid_price_string_in_custom_item(self, app, db_session):
        # A non-numeric price string in a custom item must raise TransactionError.
        items = json.dumps([
            {"product_id": None, "name": "Test", "unit": "piece", "price": "not-a-number", "quantity": 1}
        ])
        with pytest.raises(TransactionError, match="Invalid custom item price"):
            create_transaction(items, None, "full", None)

    def test_raises_for_non_integer_product_id_string(self, app, db_session):
        # A non-integer product_id string must raise TransactionError with "Invalid item data".
        items = json.dumps([{"product_id": "not-an-int", "quantity": 1}])
        with pytest.raises(TransactionError, match="Invalid item data"):
            create_transaction(items, None, "full", None)

    def test_partial_payment_with_invalid_amount_paid_defaults_to_zero(
        self, app, sample_product, db_session
    ):
        # A non-decimal amount_paid string for a partial payment must default to zero.
        items = json.dumps([{"product_id": sample_product.id, "quantity": 1}])
        tx = create_transaction(items, None, "partial", "not-a-decimal")

        assert tx.amount_paid == Decimal("0")
        assert tx.payment_status == "partial"


class TestUpdateTransaction:
    def test_updates_quantity_of_existing_item_and_recalculates_subtotal(
        self, app, sample_transaction, db_session
    ):
        existing_item = sample_transaction.items[0]
        original_price = existing_item.unit_price_snapshot  # 50.00

        items = json.dumps([
            {"item_id": existing_item.id, "product_id": existing_item.product_id, "quantity": 5}
        ])
        update_transaction(sample_transaction, items, None, "full", None)
        db_session.refresh(existing_item)

        assert existing_item.quantity == Decimal("5")
        assert existing_item.subtotal == original_price * Decimal("5")

    def test_adds_new_item_to_transaction(self, app, sample_transaction, db_session):
        existing_item = sample_transaction.items[0]
        new_product = Product(name="Mineral Water", unit="bottle", price="20.00", stock=Decimal("100"))
        db_session.add(new_product)
        db_session.commit()

        items = json.dumps([
            {"item_id": existing_item.id, "product_id": existing_item.product_id, "quantity": 2},
            {"product_id": new_product.id, "quantity": 1},
        ])
        tx = update_transaction(sample_transaction, items, None, "full", None)
        db_session.refresh(tx)

        assert len(tx.items) == 2

    def test_deletes_item_not_in_submission(self, app, sample_transaction, db_session):
        new_product = Product(name="Sparkling Water", unit="can", price="30.00", stock=Decimal("100"))
        db_session.add(new_product)
        db_session.commit()

        # Submit only the new product — no item_id for the existing item — it should be deleted
        items = json.dumps([{"product_id": new_product.id, "quantity": 1}])
        tx = update_transaction(sample_transaction, items, None, "full", None)
        db_session.refresh(tx)

        assert len(tx.items) == 1
        assert tx.items[0].product_id == new_product.id

    def test_raises_for_empty_items_list(self, app, sample_transaction, db_session):
        with pytest.raises(TransactionError, match="at least one item"):
            update_transaction(sample_transaction, json.dumps([]), None, "full", None)

    def test_raises_when_all_submitted_items_have_zero_quantity(
        self, app, sample_transaction, db_session
    ):
        existing_item = sample_transaction.items[0]
        items = json.dumps([
            {"item_id": existing_item.id, "product_id": existing_item.product_id, "quantity": 0}
        ])
        with pytest.raises(TransactionError, match="zero or negative quantity"):
            update_transaction(sample_transaction, items, None, "full", None)

    def test_update_succeeds_for_catalog_product_with_zero_price(self, app, db_session):
        # Regression: total == 0 must not be treated as "no valid items accepted"
        product = Product(name="Free Sample", unit="piece", price="0.00", stock=Decimal("10"))
        db_session.add(product)
        db_session.commit()

        tx = create_transaction(
            items_raw=json.dumps([{"product_id": product.id, "quantity": 1}]),
            customer_id=None,
            payment_status="full",
            amount_paid_raw=None,
        )

        existing_item = tx.items[0]
        items = json.dumps([
            {"item_id": existing_item.id, "product_id": product.id, "quantity": 2}
        ])

        update_transaction(tx, items, None, "full", None)

        db_session.refresh(tx)
        assert tx.items[0].quantity == Decimal("2")

    def test_raises_for_invalid_payment_status(self, app, sample_transaction, db_session):
        existing_item = sample_transaction.items[0]
        items = json.dumps([
            {"item_id": existing_item.id, "product_id": existing_item.product_id, "quantity": 1}
        ])
        with pytest.raises(TransactionError, match="Invalid payment status"):
            update_transaction(sample_transaction, items, None, "bad_status", None)

    def test_raises_for_malformed_json(self, app, sample_transaction, db_session):
        with pytest.raises(TransactionError, match="Invalid item data"):
            update_transaction(sample_transaction, "broken{{json", None, "full", None)

    def test_item_with_zero_quantity_is_skipped(self, app, sample_transaction, db_session):
        existing_item = sample_transaction.items[0]
        new_product = Product(name="Sparkling Water", unit="can", price="30.00")
        db_session.add(new_product)
        db_session.commit()

        items = json.dumps([
            {"item_id": existing_item.id, "product_id": existing_item.product_id, "quantity": 2},
            {"product_id": new_product.id, "quantity": 0},
        ])
        tx = update_transaction(sample_transaction, items, None, "full", None)
        db_session.refresh(tx)

        assert len(tx.items) == 1
        assert tx.items[0].quantity == Decimal("2")

    def test_raises_for_nonexistent_product_when_adding_new_item(self, app, sample_transaction, db_session):
        items = json.dumps([{"product_id": 99999, "quantity": 1}])
        with pytest.raises(TransactionError, match="not found"):
            update_transaction(sample_transaction, items, None, "full", None)

    def test_raises_for_invalid_quantity_in_update(self, app, sample_transaction, db_session):
        existing_item = sample_transaction.items[0]
        items = json.dumps([{"item_id": existing_item.id, "quantity": "bad-qty"}])
        with pytest.raises(TransactionError, match="Invalid quantity"):
            update_transaction(sample_transaction, items, None, "full", None)

    def test_update_restores_stock_when_quantity_decreased(self, app, db_session):
        # stock=15 so create_transaction (qty=5) brings it to 10, leaving room for the delta
        product = Product(name="Direct Stock Product", unit="bottle", price="10.00", stock=Decimal("15"))
        db_session.add(product)
        db_session.commit()

        items_raw = json.dumps([{"product_id": product.id, "quantity": 5}])
        tx = create_transaction(items_raw, None, "full", None)
        db_session.refresh(product)
        assert product.stock == Decimal("10")  # sanity check: create deducted 5

        existing_item = tx.items[0]
        update_items = json.dumps([
            {"item_id": existing_item.id, "product_id": product.id, "quantity": 3}
        ])
        update_transaction(tx, update_items, None, "full", None)
        db_session.refresh(product)

        # delta = 3 - 5 = -2 (restore 2); 10 + 2 = 12
        assert product.stock == Decimal("12")

    def test_update_deducts_stock_when_quantity_increased(self, app, db_session):
        # stock=15 so create_transaction (qty=5) brings it to 10
        product = Product(name="Direct Stock Product", unit="bottle", price="10.00", stock=Decimal("15"))
        db_session.add(product)
        db_session.commit()

        items_raw = json.dumps([{"product_id": product.id, "quantity": 5}])
        tx = create_transaction(items_raw, None, "full", None)
        db_session.refresh(product)
        assert product.stock == Decimal("10")  # sanity check

        existing_item = tx.items[0]
        update_items = json.dumps([
            {"item_id": existing_item.id, "product_id": product.id, "quantity": 7}
        ])
        update_transaction(tx, update_items, None, "full", None)
        db_session.refresh(product)

        # delta = 7 - 5 = +2 (deduct 2 more); 10 - 2 = 8
        assert product.stock == Decimal("8")

    def test_update_restores_stock_when_item_deleted(self, app, db_session):
        # stock=10; create deducts 5 → stock=5; removing the item restores 5 → stock=10
        product = Product(name="Direct Stock Product", unit="bottle", price="10.00", stock=Decimal("10"))
        db_session.add(product)
        db_session.commit()

        items_raw = json.dumps([{"product_id": product.id, "quantity": 5}])
        tx = create_transaction(items_raw, None, "full", None)
        db_session.refresh(product)
        assert product.stock == Decimal("5")  # sanity check

        # Submit only a custom ad-hoc item — the catalog item has no item_id submitted, so it is deleted
        update_items = json.dumps([
            {"product_id": None, "name": "Ad-hoc Water", "unit": "bottle", "price": "10.00", "quantity": 1}
        ])
        update_transaction(tx, update_items, None, "full", None)
        db_session.refresh(product)

        assert product.stock == Decimal("10")

    def test_update_does_not_adjust_stock_for_non_sale_transaction(self, app, sample_vendor, db_session):
        product = Product(name="Direct Stock Product", unit="bottle", price="10.00", stock=Decimal("5"))
        db_session.add(product)
        db_session.commit()

        # Build a restock transaction manually
        tx = Transaction(
            transaction_type="restock",
            vendor_id=sample_vendor.id,
            total_amount="50.00",
            amount_paid="50.00",
            payment_status="full",
        )
        db_session.add(tx)
        db_session.flush()
        item = TransactionItem(
            transaction_id=tx.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            unit_snapshot=product.unit,
            unit_price_snapshot="10.00",
            quantity="5",
            subtotal="50.00",
        )
        db_session.add(item)
        db_session.commit()

        update_items = json.dumps([
            {"item_id": item.id, "product_id": product.id, "quantity": 3}
        ])
        update_transaction(tx, update_items, None, "full", None)
        db_session.refresh(product)

        assert product.stock == Decimal("5")

    def test_update_raises_when_new_item_exceeds_available_stock(self, app, db_session):
        # Create a sale transaction using a custom item so no stock is deducted during create
        tx_items_raw = json.dumps([
            {"product_id": None, "name": "Ad-hoc", "unit": "bottle", "price": "10.00", "quantity": 1}
        ])
        tx = create_transaction(tx_items_raw, None, "full", None)

        # Product with only 3 units available
        product = Product(name="Low Stock Product", unit="bottle", price="10.00", stock=Decimal("3"))
        db_session.add(product)
        db_session.commit()

        # Try to add a new catalog item requiring 5 units (exceeds available stock of 3)
        update_items = json.dumps([{"product_id": product.id, "quantity": 5}])
        with pytest.raises(TransactionError, match="only has"):
            update_transaction(tx, update_items, None, "full", None)

    def test_raises_when_new_custom_item_has_invalid_price_string(
        self, app, sample_transaction, db_session
    ):
        # A non-numeric price string on a new custom item in update must raise TransactionError.
        items = json.dumps([
            {"product_id": None, "name": "Custom", "unit": "piece", "price": "bad-price", "quantity": 1}
        ])
        with pytest.raises(TransactionError, match="Invalid custom item price"):
            update_transaction(sample_transaction, items, None, "full", None)

    def test_raises_when_new_custom_item_is_missing_name_in_update(
        self, app, sample_transaction, db_session
    ):
        # Triggers the name/unit/price > 0 validation in the new-item custom branch.
        items = json.dumps([
            {"product_id": None, "name": "", "unit": "bottle", "price": "5.00", "quantity": 1}
        ])
        with pytest.raises(TransactionError, match="Custom item requires"):
            update_transaction(sample_transaction, items, None, "full", None)

    def test_raises_when_new_catalog_item_has_non_integer_product_id(
        self, app, sample_transaction, db_session
    ):
        # A non-integer product_id string on a new catalog item in update must raise TransactionError.
        items = json.dumps([{"product_id": "not-an-int", "quantity": 1}])
        with pytest.raises(TransactionError, match="Invalid product"):
            update_transaction(sample_transaction, items, None, "full", None)

    def test_commit_failure_rolls_back_and_raises_in_update_transaction(
        self, app, sample_transaction, db_session
    ):
        existing_item = sample_transaction.items[0]
        items = json.dumps([
            {"item_id": existing_item.id, "product_id": existing_item.product_id, "quantity": 1}
        ])
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                update_transaction(sample_transaction, items, None, "full", None)
        mock_rollback.assert_called_once()


class TestUpdateTransactionIngredients:
    """Tests for update_transaction paths that exercise ingredient-based stock adjustment."""

    @pytest.fixture
    def ingredient_product(self, db_session, sample_stock_item):
        """A product that consumes 2 liters of sample_stock_item per unit sold."""
        from app.models.stock import ProductIngredient

        product = Product(
            name="Ingredient Bottled Water", unit="bottle", price="15.00", stock=Decimal("0")
        )
        db_session.add(product)
        db_session.flush()
        ing = ProductIngredient(
            product_id=product.id,
            stock_item_id=sample_stock_item.id,
            quantity=Decimal("2"),
        )
        db_session.add(ing)
        db_session.commit()
        return product

    def test_update_adjusts_ingredient_stock_when_quantity_decreased(
        self, app, ingredient_product, sample_stock_item, db_session
    ):
        # Create: 5 bottles → 10L deducted → 10L remaining
        items_raw = json.dumps([{"product_id": ingredient_product.id, "quantity": 5}])
        tx = create_transaction(items_raw, None, "full", None)
        db_session.refresh(sample_stock_item)
        assert sample_stock_item.quantity == Decimal("10")  # sanity

        # Update to 3 bottles: delta=-2, restores 4L (2*2) → 14L
        existing_item = tx.items[0]
        update_items = json.dumps([
            {"item_id": existing_item.id, "product_id": ingredient_product.id, "quantity": 3}
        ])
        update_transaction(tx, update_items, None, "full", None)
        db_session.refresh(sample_stock_item)

        assert sample_stock_item.quantity == Decimal("14")

    def test_update_adjusts_ingredient_stock_when_quantity_increased(
        self, app, ingredient_product, sample_stock_item, db_session
    ):
        # Create: 3 bottles → 6L deducted → 14L remaining
        items_raw = json.dumps([{"product_id": ingredient_product.id, "quantity": 3}])
        tx = create_transaction(items_raw, None, "full", None)
        db_session.refresh(sample_stock_item)
        assert sample_stock_item.quantity == Decimal("14")  # sanity

        # Update to 5 bottles: delta=+2, deducts 4L more (2*2) → 10L
        existing_item = tx.items[0]
        update_items = json.dumps([
            {"item_id": existing_item.id, "product_id": ingredient_product.id, "quantity": 5}
        ])
        update_transaction(tx, update_items, None, "full", None)
        db_session.refresh(sample_stock_item)

        assert sample_stock_item.quantity == Decimal("10")

    def test_update_raises_when_ingredient_stock_insufficient_for_increased_quantity(
        self, app, ingredient_product, sample_stock_item, db_session
    ):
        # Create: 9 bottles → 18L deducted → 2L remaining
        items_raw = json.dumps([{"product_id": ingredient_product.id, "quantity": 9}])
        tx = create_transaction(items_raw, None, "full", None)
        db_session.refresh(sample_stock_item)
        assert sample_stock_item.quantity == Decimal("2")  # sanity

        # Update to 11 bottles: delta=+2, needs 4L (2*2) but only 2L available → raises
        existing_item = tx.items[0]
        update_items = json.dumps([
            {"item_id": existing_item.id, "product_id": ingredient_product.id, "quantity": 11}
        ])
        with pytest.raises(TransactionError, match="Not enough"):
            update_transaction(tx, update_items, None, "full", None)

    def test_update_restores_ingredient_stock_when_item_deleted(
        self, app, ingredient_product, sample_stock_item, db_session
    ):
        # Create: 5 bottles → 10L deducted → 10L remaining
        items_raw = json.dumps([{"product_id": ingredient_product.id, "quantity": 5}])
        tx = create_transaction(items_raw, None, "full", None)
        db_session.refresh(sample_stock_item)
        assert sample_stock_item.quantity == Decimal("10")  # sanity

        # Replace with ad-hoc item — existing catalog item deleted → delta=-5 → restores 10L → 20L
        update_items = json.dumps([
            {"product_id": None, "name": "Ad-hoc", "unit": "bottle", "price": "10.00", "quantity": 1}
        ])
        update_transaction(tx, update_items, None, "full", None)
        db_session.refresh(sample_stock_item)

        assert sample_stock_item.quantity == Decimal("20")


class TestCreateRestock:
    def test_unit_price_snapshot_uses_submitted_unit_price_not_product_price(
        self, app, sample_product, sample_vendor, db_session
    ):
        # sample_product.price is 50.00; submit a vendor cost of 30.00
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 2, "unit_price": "30.00"}
        ])
        tx = create_restock(items, str(sample_vendor.id), "full", None)

        assert len(tx.items) == 1
        item = tx.items[0]
        assert item.unit_price_snapshot == Decimal("30.00")
        assert item.unit_price_snapshot != sample_product.price
        assert item.subtotal == Decimal("60.00")

    def test_raises_when_unit_price_missing_from_item(
        self, app, sample_product, sample_vendor, db_session
    ):
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 1}
        ])
        with pytest.raises(TransactionError, match="Invalid item data"):
            create_restock(items, str(sample_vendor.id), "full", None)

    def test_raises_when_unit_price_is_negative(
        self, app, sample_product, sample_vendor, db_session
    ):
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 1, "unit_price": "-5.00"}
        ])
        with pytest.raises(TransactionError, match="Unit price must be"):
            create_restock(items, str(sample_vendor.id), "full", None)

    def test_raises_for_invalid_payment_status_in_create_restock(
        self, app, sample_product, sample_vendor, db_session
    ):
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 1, "unit_price": "10.00"}
        ])
        with pytest.raises(TransactionError, match="Invalid payment status"):
            create_restock(items, str(sample_vendor.id), "cash", None)

    def test_raises_when_adhoc_item_included_in_restock_cart(
        self, app, sample_vendor, db_session
    ):
        # Restock items must all be catalog products — ad-hoc entries must be rejected.
        items = json.dumps([
            {"product_id": None, "name": "Custom", "unit": "piece", "price": "10.00", "quantity": 1}
        ])
        with pytest.raises(TransactionError, match="catalog products"):
            create_restock(items, str(sample_vendor.id), "full", None)

    def test_raises_when_restock_item_quantity_is_zero(
        self, app, sample_product, sample_vendor, db_session
    ):
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 0, "unit_price": "10.00"}
        ])
        with pytest.raises(TransactionError, match="Quantity must be greater than zero"):
            create_restock(items, str(sample_vendor.id), "full", None)

    def test_raises_when_restock_product_not_found(
        self, app, sample_vendor, db_session
    ):
        items = json.dumps([
            {"product_id": 99999, "quantity": 1, "unit_price": "10.00"}
        ])
        with pytest.raises(TransactionError, match="not found"):
            create_restock(items, str(sample_vendor.id), "full", None)

    def test_raises_when_vendor_id_is_not_an_integer(
        self, app, sample_product, db_session
    ):
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 1, "unit_price": "10.00"}
        ])
        with pytest.raises(TransactionError, match="vendor must be selected"):
            create_restock(items, "not-an-int", "full", None)

    def test_raises_when_vendor_not_found(
        self, app, sample_product, db_session
    ):
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 1, "unit_price": "10.00"}
        ])
        with pytest.raises(TransactionError, match="Vendor not found"):
            create_restock(items, "99999", "full", None)

    def test_raises_when_items_json_is_malformed(
        self, app, sample_vendor, db_session
    ):
        with pytest.raises(TransactionError, match="Invalid cart data"):
            create_restock("not-valid-json{{", str(sample_vendor.id), "full", None)

    def test_raises_when_restock_cart_is_empty(
        self, app, sample_vendor, db_session
    ):
        with pytest.raises(TransactionError, match="Cart is empty"):
            create_restock(json.dumps([]), str(sample_vendor.id), "full", None)

    def test_commit_failure_rolls_back_and_raises_in_create_restock(
        self, app, sample_product, sample_vendor, db_session
    ):
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 1, "unit_price": "10.00"}
        ])
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                create_restock(items, str(sample_vendor.id), "full", None)
        mock_rollback.assert_called_once()

    def test_product_stock_is_incremented_after_successful_restock(
        self, app, sample_product, sample_vendor, db_session
    ):
        initial_stock = sample_product.stock
        items = json.dumps([
            {"product_id": sample_product.id, "quantity": 5, "unit_price": "10.00"}
        ])
        create_restock(items, str(sample_vendor.id), "full", None)
        db_session.refresh(sample_product)

        assert sample_product.stock == initial_stock + Decimal("5")


class TestCreateStockRestockEdgeCases:
    """Coverage for branches in create_stock_restock not exercised by the stock test suite."""

    def test_raises_for_invalid_payment_status_in_create_stock_restock(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "5.00"}
        ])
        with pytest.raises(TransactionError, match="Invalid payment status"):
            create_stock_restock(items, str(sample_vendor.id), "cash", None)

    def test_raises_when_stock_restock_items_json_is_malformed(
        self, app, sample_vendor, db_session
    ):
        with pytest.raises(TransactionError, match="Invalid cart data"):
            create_stock_restock("bad-json{{", str(sample_vendor.id), "full", None)

    def test_raises_for_invalid_item_data_parsing_in_stock_restock(
        self, app, sample_vendor, db_session
    ):
        # Missing stock_item_id key triggers KeyError inside the try block.
        items = json.dumps([{"quantity": "5", "unit_price": "5.00"}])
        with pytest.raises(TransactionError, match="Invalid item data"):
            create_stock_restock(items, str(sample_vendor.id), "full", None)

    def test_raises_when_stock_restock_unit_price_is_negative(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        # unit_price < 0 branch of `if quantity <= 0 or unit_price < 0`.
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "-1.00"}
        ])
        with pytest.raises(TransactionError, match="price must be"):
            create_stock_restock(items, str(sample_vendor.id), "full", None)

    def test_commit_failure_rolls_back_and_raises_in_create_stock_restock(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "5.00"}
        ])
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                create_stock_restock(items, str(sample_vendor.id), "full", None)
        mock_rollback.assert_called_once()

    def test_happy_path_increments_stock_item_quantity_and_returns_correct_transaction(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "5.00"}
        ])
        tx = create_stock_restock(items, str(sample_vendor.id), "full", None)
        db_session.refresh(sample_stock_item)

        assert sample_stock_item.quantity == Decimal("25")
        assert tx.total_amount == Decimal("25.00")
        assert len(tx.items) == 1
        assert tx.items[0].unit_price_snapshot == Decimal("5.00")
