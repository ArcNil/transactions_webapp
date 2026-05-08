import json
from decimal import Decimal

import pytest

from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient
from app.models.transaction import Transaction
from app.services.transaction_service import (
    TransactionError,
    _check_ingredient_stock,
    _deduct_ingredient_stock,
    create_stock_restock,
    create_transaction,
)


@pytest.fixture
def ingredient_product(db_session, sample_stock_item):
    """A Product that consumes 2 liters of sample_stock_item per unit sold."""
    product = Product(name="Bottled Water", unit="bottle", price="15.00", stock=Decimal("0"))
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


class TestCheckIngredientStock:
    def test_passes_when_stock_is_sufficient(self, app, ingredient_product, sample_stock_item):
        # sample_stock_item has 20 liters, product needs 2 per bottle → can make 10
        _check_ingredient_stock(ingredient_product, Decimal("5"))  # needs 10 liters — no error

    def test_passes_at_exact_stock_boundary(self, app, ingredient_product, sample_stock_item):
        # needs 2 * 10 = 20 liters, have exactly 20 → should pass
        _check_ingredient_stock(ingredient_product, Decimal("10"))

    def test_raises_when_stock_is_insufficient(self, app, ingredient_product, sample_stock_item):
        # needs 2 * 11 = 22 liters, have 20 → insufficient
        with pytest.raises(TransactionError):
            _check_ingredient_stock(ingredient_product, Decimal("11"))

    def test_error_message_includes_product_name(self, app, ingredient_product, sample_stock_item):
        with pytest.raises(TransactionError, match=ingredient_product.name):
            _check_ingredient_stock(ingredient_product, Decimal("11"))

    def test_error_message_includes_stock_item_name(self, app, ingredient_product, sample_stock_item):
        with pytest.raises(TransactionError, match=sample_stock_item.name):
            _check_ingredient_stock(ingredient_product, Decimal("11"))


class TestDeductIngredientStock:
    def test_decrements_stock_item_by_ingredient_quantity_times_sold(
        self, app, ingredient_product, sample_stock_item, db_session
    ):
        _deduct_ingredient_stock(ingredient_product, Decimal("3"))
        db_session.flush()
        db_session.refresh(sample_stock_item)

        # 20 - 2 * 3 = 14
        assert sample_stock_item.quantity == Decimal("14")

    def test_deducts_full_quantity_when_selling_maximum(
        self, app, ingredient_product, sample_stock_item, db_session
    ):
        _deduct_ingredient_stock(ingredient_product, Decimal("10"))
        db_session.flush()
        db_session.refresh(sample_stock_item)

        # 20 - 2 * 10 = 0
        assert sample_stock_item.quantity == Decimal("0")

    def test_decrements_multiple_ingredients_independently(self, app, db_session):
        product = Product(name="Mix Drink", unit="cup", price="25.00", stock=Decimal("0"))
        item_a = StockItem(name="Syrup", unit="ml", quantity=Decimal("100"))
        item_b = StockItem(name="Sparkling Water", unit="ml", quantity=Decimal("500"))
        db_session.add_all([product, item_a, item_b])
        db_session.flush()

        ing_a = ProductIngredient(
            product_id=product.id, stock_item_id=item_a.id, quantity=Decimal("10")
        )
        ing_b = ProductIngredient(
            product_id=product.id, stock_item_id=item_b.id, quantity=Decimal("50")
        )
        db_session.add_all([ing_a, ing_b])
        db_session.commit()

        _deduct_ingredient_stock(product, Decimal("2"))

        db_session.refresh(item_a)
        db_session.refresh(item_b)
        # syrup: 100 - 10 * 2 = 80, water: 500 - 50 * 2 = 400
        assert item_a.quantity == Decimal("80")
        assert item_b.quantity == Decimal("400")


class TestCreateTransactionWithIngredients:
    def test_deducts_raw_ingredient_stock_not_product_stock(
        self, app, ingredient_product, sample_stock_item, db_session
    ):
        initial_product_stock = ingredient_product.stock
        items = json.dumps([{"product_id": ingredient_product.id, "quantity": 3}])
        create_transaction(items, None, "full", None)

        db_session.refresh(ingredient_product)
        db_session.refresh(sample_stock_item)
        # product.stock unchanged; stock_item.quantity reduced by 2 * 3 = 6
        assert ingredient_product.stock == initial_product_stock
        assert sample_stock_item.quantity == Decimal("14")

    def test_creates_transaction_with_correct_item_snapshot(
        self, app, ingredient_product, db_session
    ):
        items = json.dumps([{"product_id": ingredient_product.id, "quantity": 2}])
        tx = create_transaction(items, None, "full", None)

        assert len(tx.items) == 1
        item = tx.items[0]
        assert item.product_id == ingredient_product.id
        assert item.quantity == Decimal("2")
        assert item.product_name_snapshot == ingredient_product.name

    def test_raises_when_ingredient_stock_is_insufficient(
        self, app, ingredient_product, sample_stock_item
    ):
        # have 20 liters, need 2 * 11 = 22
        items = json.dumps([{"product_id": ingredient_product.id, "quantity": 11}])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_total_amount_calculated_from_product_price_not_ingredient_value(
        self, app, ingredient_product, db_session
    ):
        items = json.dumps([{"product_id": ingredient_product.id, "quantity": 4}])
        tx = create_transaction(items, None, "full", None)

        # 4 bottles * 15.00 = 60.00
        assert tx.total_amount == Decimal("60.00")


class TestCreateTransactionWithoutIngredients:
    def test_deducts_product_stock_directly(self, app, sample_product, db_session):
        sample_product.stock = Decimal("10")
        db_session.commit()

        items = json.dumps([{"product_id": sample_product.id, "quantity": 3}])
        create_transaction(items, None, "full", None)

        db_session.refresh(sample_product)
        assert sample_product.stock == Decimal("7")

    def test_raises_when_product_stock_is_insufficient(self, app, sample_product, db_session):
        sample_product.stock = Decimal("2")
        db_session.commit()

        items = json.dumps([{"product_id": sample_product.id, "quantity": 5}])
        with pytest.raises(TransactionError):
            create_transaction(items, None, "full", None)

    def test_stock_reaches_zero_at_exact_boundary(self, app, sample_product, db_session):
        sample_product.stock = Decimal("5")
        db_session.commit()

        items = json.dumps([{"product_id": sample_product.id, "quantity": 5}])
        create_transaction(items, None, "full", None)

        db_session.refresh(sample_product)
        assert sample_product.stock == Decimal("0")


class TestCreateStockRestock:
    def test_increments_stock_item_quantity(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "10", "unit_price": "5.00"}
        ])
        create_stock_restock(items, str(sample_vendor.id), "full", None)

        db_session.refresh(sample_stock_item)
        assert sample_stock_item.quantity == Decimal("30")  # 20 + 10

    def test_creates_transaction_of_type_stock_restock(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "8.00"}
        ])
        tx = create_stock_restock(items, str(sample_vendor.id), "full", None)

        assert tx.transaction_type == "stock_restock"
        assert tx.vendor_id == sample_vendor.id

    def test_creates_transaction_item_referencing_stock_item(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "4", "unit_price": "10.00"}
        ])
        tx = create_stock_restock(items, str(sample_vendor.id), "full", None)

        assert len(tx.items) == 1
        assert tx.items[0].stock_item_id == sample_stock_item.id
        assert tx.items[0].quantity == Decimal("4")

    def test_total_amount_is_quantity_times_unit_price(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "4", "unit_price": "10.00"}
        ])
        tx = create_stock_restock(items, str(sample_vendor.id), "full", None)

        assert tx.total_amount == Decimal("40.00")
        assert tx.amount_paid == Decimal("40.00")

    def test_sets_amount_paid_to_zero_when_unpaid(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "2", "unit_price": "5.00"}
        ])
        tx = create_stock_restock(items, str(sample_vendor.id), "unpaid", None)

        assert tx.amount_paid == Decimal("0")
        assert tx.payment_status == "unpaid"

    def test_raises_when_vendor_id_is_not_an_integer(self, app, sample_stock_item):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "5.00"}
        ])
        with pytest.raises(TransactionError, match="vendor"):
            create_stock_restock(items, "not-an-int", "full", None)

    def test_raises_when_vendor_not_found(self, app, sample_stock_item):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "5.00"}
        ])
        with pytest.raises(TransactionError, match="Vendor not found"):
            create_stock_restock(items, "99999", "full", None)

    def test_raises_when_cart_is_empty(self, app, sample_vendor):
        with pytest.raises(TransactionError, match="Cart is empty"):
            create_stock_restock(json.dumps([]), str(sample_vendor.id), "full", None)

    def test_raises_when_stock_item_not_found(self, app, sample_vendor):
        items = json.dumps([
            {"stock_item_id": 99999, "quantity": "5", "unit_price": "5.00"}
        ])
        with pytest.raises(TransactionError):
            create_stock_restock(items, str(sample_vendor.id), "full", None)

    def test_raises_when_quantity_is_zero(self, app, sample_vendor, sample_stock_item):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "0", "unit_price": "5.00"}
        ])
        with pytest.raises(TransactionError):
            create_stock_restock(items, str(sample_vendor.id), "full", None)

    def test_raises_for_invalid_payment_status(self, app, sample_vendor, sample_stock_item):
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "3", "unit_price": "5.00"}
        ])
        with pytest.raises(TransactionError):
            create_stock_restock(items, str(sample_vendor.id), "invalid_status", None)

    def test_unit_price_snapshot_matches_submitted_unit_price(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        # The frontend sends unit_price (computed as totalPrice / qty).
        # Verify the service stores that exact value as unit_price_snapshot.
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "4", "unit_price": "8.50"}
        ])
        tx = create_stock_restock(items, str(sample_vendor.id), "full", None)

        assert tx.items[0].unit_price_snapshot == Decimal("8.50")

    def test_unit_price_snapshot_accepts_value_derived_from_total_divided_by_qty(
        self, app, sample_vendor, sample_stock_item, db_session
    ):
        # Mirrors JS logic: user entered totalPrice=100, qty=4 → unit_price = 25.00.
        # The route receives unit_price, not total_price.
        items = json.dumps([
            {"stock_item_id": sample_stock_item.id, "quantity": "4", "unit_price": "25.00"}
        ])
        tx = create_stock_restock(items, str(sample_vendor.id), "full", None)

        assert tx.items[0].unit_price_snapshot == Decimal("25.00")
        assert tx.total_amount == Decimal("100.00")

    def test_multiple_items_all_incremented_and_snapshots_are_correct(
        self, app, sample_vendor, db_session
    ):
        item_a = StockItem(name="Salt", unit="kg", quantity=Decimal("10"))
        item_b = StockItem(name="Sugar", unit="kg", quantity=Decimal("5"))
        db_session.add_all([item_a, item_b])
        db_session.commit()

        items = json.dumps([
            {"stock_item_id": item_a.id, "quantity": "3", "unit_price": "20.00"},
            {"stock_item_id": item_b.id, "quantity": "2", "unit_price": "30.00"},
        ])
        tx = create_stock_restock(items, str(sample_vendor.id), "full", None)

        db_session.refresh(item_a)
        db_session.refresh(item_b)
        assert item_a.quantity == Decimal("13")  # 10 + 3
        assert item_b.quantity == Decimal("7")   # 5 + 2

        assert len(tx.items) == 2
        snapshots = {i.stock_item_id: i.unit_price_snapshot for i in tx.items}
        assert snapshots[item_a.id] == Decimal("20.00")
        assert snapshots[item_b.id] == Decimal("30.00")
