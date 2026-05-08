import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.models.stock import StockItem, ProductIngredient
from app.models.product import Product


class TestStockItem:
    def test_stock_item_can_be_created_with_required_fields(self, db_session):
        item = StockItem(name="Distilled Water", unit="liter")
        db_session.add(item)
        db_session.commit()

        saved = db_session.get(StockItem, item.id)
        assert saved.name == "Distilled Water"
        assert saved.unit == "liter"

    def test_quantity_defaults_to_zero(self, db_session):
        item = StockItem(name="Salt", unit="kg")
        db_session.add(item)
        db_session.commit()

        assert item.quantity == Decimal("0")

    def test_vendor_id_is_nullable(self, db_session):
        item = StockItem(name="Sugar", unit="kg", vendor_id=None)
        db_session.add(item)
        db_session.commit()

        assert item.vendor_id is None

    def test_created_at_is_set_automatically(self, db_session):
        item = StockItem(name="Citric Acid", unit="g")
        db_session.add(item)
        db_session.commit()

        assert item.created_at is not None

    def test_name_cannot_be_null(self, db_session):
        item = StockItem(name=None, unit="kg")
        db_session.add(item)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unit_cannot_be_null(self, db_session):
        item = StockItem(name="Salt", unit=None)
        db_session.add(item)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_quantity_can_be_set_on_creation(self, db_session):
        item = StockItem(name="Base Water", unit="liter", quantity=Decimal("100.5"))
        db_session.add(item)
        db_session.commit()

        assert item.quantity == Decimal("100.5")


class TestProductIngredient:
    def test_product_ingredient_links_product_and_stock_item(self, db_session):
        product = Product(name="Flavored Water", unit="bottle", price="30.00")
        stock_item = StockItem(name="Water Base", unit="liter")
        db_session.add_all([product, stock_item])
        db_session.flush()

        ing = ProductIngredient(
            product_id=product.id,
            stock_item_id=stock_item.id,
            quantity=Decimal("0.5"),
        )
        db_session.add(ing)
        db_session.commit()

        saved = db_session.get(ProductIngredient, ing.id)
        assert saved.product_id == product.id
        assert saved.stock_item_id == stock_item.id
        assert saved.quantity == Decimal("0.5")

    def test_product_ingredient_back_populates_product_ingredients_list(self, db_session):
        product = Product(name="Premium Water", unit="gallon", price="50.00")
        stock_item = StockItem(name="Pure Water", unit="liter", quantity=Decimal("100"))
        db_session.add_all([product, stock_item])
        db_session.flush()

        ing = ProductIngredient(
            product_id=product.id,
            stock_item_id=stock_item.id,
            quantity=Decimal("3.5"),
        )
        db_session.add(ing)
        db_session.commit()

        assert len(product.ingredients) == 1
        assert product.ingredients[0].stock_item.name == "Pure Water"

    def test_stock_item_back_populates_ingredients_list(self, db_session):
        product = Product(name="Test Drink", unit="cup", price="10.00")
        stock_item = StockItem(name="Syrup", unit="ml")
        db_session.add_all([product, stock_item])
        db_session.flush()

        ing = ProductIngredient(
            product_id=product.id,
            stock_item_id=stock_item.id,
            quantity=Decimal("20"),
        )
        db_session.add(ing)
        db_session.commit()

        assert len(stock_item.ingredients) == 1
        assert stock_item.ingredients[0].product.name == "Test Drink"

    def test_quantity_cannot_be_null(self, db_session):
        product = Product(name="Test", unit="unit", price="10.00")
        stock_item = StockItem(name="Base", unit="kg")
        db_session.add_all([product, stock_item])
        db_session.flush()

        ing = ProductIngredient(
            product_id=product.id,
            stock_item_id=stock_item.id,
            quantity=None,
        )
        db_session.add(ing)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_deleting_product_cascades_to_ingredients(self, db_session):
        product = Product(name="Cascade Test", unit="unit", price="5.00")
        stock_item = StockItem(name="Raw Material", unit="g")
        db_session.add_all([product, stock_item])
        db_session.flush()

        ing = ProductIngredient(
            product_id=product.id,
            stock_item_id=stock_item.id,
            quantity=Decimal("1"),
        )
        db_session.add(ing)
        db_session.commit()
        ing_id = ing.id

        db_session.delete(product)
        db_session.commit()

        assert db_session.get(ProductIngredient, ing_id) is None


class TestProductAvailableStock:
    def test_returns_product_stock_when_no_ingredients(self, db_session):
        product = Product(name="Direct Stock Product", unit="bottle", price="10.00", stock=Decimal("25"))
        db_session.add(product)
        db_session.commit()

        assert product.available_stock == Decimal("25")

    def test_returns_derived_stock_based_on_single_ingredient(self, db_session):
        product = Product(name="Bottled Water", unit="bottle", price="20.00", stock=Decimal("0"))
        stock_item = StockItem(name="Raw Water", unit="liter", quantity=Decimal("10"))
        db_session.add_all([product, stock_item])
        db_session.flush()

        # 1 bottle requires 2 liters → floor(10 / 2) = 5 bottles available
        ing = ProductIngredient(
            product_id=product.id, stock_item_id=stock_item.id, quantity=Decimal("2")
        )
        db_session.add(ing)
        db_session.commit()

        assert product.available_stock == 5

    def test_returns_minimum_across_multiple_ingredients(self, db_session):
        product = Product(name="Multi-Ingredient Drink", unit="cup", price="15.00", stock=Decimal("0"))
        item_a = StockItem(name="Ingredient A", unit="kg", quantity=Decimal("30"))
        item_b = StockItem(name="Ingredient B", unit="liter", quantity=Decimal("5"))
        db_session.add_all([product, item_a, item_b])
        db_session.flush()

        # floor(30 / 3) = 10 from A, floor(5 / 2.5) = 2 from B → min = 2
        ing_a = ProductIngredient(
            product_id=product.id, stock_item_id=item_a.id, quantity=Decimal("3")
        )
        ing_b = ProductIngredient(
            product_id=product.id, stock_item_id=item_b.id, quantity=Decimal("2.5")
        )
        db_session.add_all([ing_a, ing_b])
        db_session.commit()

        assert product.available_stock == 2

    def test_returns_zero_when_one_ingredient_stock_is_empty(self, db_session):
        product = Product(name="Zero Ingredient", unit="bag", price="5.00", stock=Decimal("100"))
        stock_item = StockItem(name="Empty Ingredient", unit="kg", quantity=Decimal("0"))
        db_session.add_all([product, stock_item])
        db_session.flush()

        ing = ProductIngredient(
            product_id=product.id, stock_item_id=stock_item.id, quantity=Decimal("1")
        )
        db_session.add(ing)
        db_session.commit()

        assert product.available_stock == 0

    def test_floors_fractional_yield(self, db_session):
        product = Product(name="Fractional Yield", unit="unit", price="10.00", stock=Decimal("0"))
        stock_item = StockItem(name="Partial Stock", unit="liter", quantity=Decimal("7"))
        db_session.add_all([product, stock_item])
        db_session.flush()

        # floor(7 / 3) = 2 (not 2.33)
        ing = ProductIngredient(
            product_id=product.id, stock_item_id=stock_item.id, quantity=Decimal("3")
        )
        db_session.add(ing)
        db_session.commit()

        assert product.available_stock == 2
