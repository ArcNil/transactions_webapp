import json
from decimal import Decimal

from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient
from app.models.transaction import Transaction, TransactionItem


def test_pos_index_returns_200_for_authenticated_user(logged_in_client):
    response = logged_in_client.get("/pos/")
    assert response.status_code == 200


def test_pos_index_redirects_to_login_if_anonymous(client):
    response = client.get("/pos/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_pos_save_with_catalog_product_creates_transaction_and_item(
    logged_in_client, sample_product, db_session
):
    items = json.dumps([{"product_id": sample_product.id, "quantity": "2"}])
    response = logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Transaction saved!" in response.data

    tx = Transaction.query.first()
    assert tx is not None
    assert len(tx.items) == 1
    assert tx.items[0].product_name_snapshot == sample_product.name


def test_pos_save_with_custom_item_creates_transaction_and_item(
    logged_in_client, db_session
):
    items = json.dumps(
        [
            {
                "product_id": None,
                "name": "Special Delivery",
                "unit": "trip",
                "price": "150.00",
                "quantity": "1",
            }
        ]
    )
    response = logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Transaction saved!" in response.data

    tx = Transaction.query.first()
    assert tx is not None
    assert len(tx.items) == 1
    assert tx.items[0].product_name_snapshot == "Special Delivery"
    assert tx.items[0].product_id is None


def test_pos_save_with_empty_cart_flashes_cart_is_empty(logged_in_client):
    response = logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",
            "items": json.dumps([]),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Cart is empty." in response.data


def test_pos_save_with_nonexistent_product_flashes_error(logged_in_client):
    items = json.dumps([{"product_id": 99999, "quantity": "1"}])
    response = logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"not found" in response.data


def test_pos_save_with_malformed_json_items_flashes_error(logged_in_client):
    response = logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",
            "items": "this-is-not-json",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid cart data." in response.data


def test_pos_product_no_ingredients_in_stock_renders_as_available(
    logged_in_client, db_session
):
    product = Product(name="Bottled Water", unit="bottle", price="15.00", stock=5)
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/pos/")
    assert response.status_code == 200
    assert b"Out of stock" not in response.data
    assert b"bottle(s) left" in response.data


def test_pos_product_no_ingredients_zero_stock_renders_out_of_stock(
    logged_in_client, db_session
):
    product = Product(name="Bottled Water", unit="bottle", price="15.00", stock=0)
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/pos/")
    assert response.status_code == 200
    assert b"Out of stock" in response.data
    assert b"disabled opacity-50" in response.data


def test_pos_product_with_ingredients_sufficient_stock_renders_as_available(
    logged_in_client, db_session
):
    product = Product(name="Refill Gallon", unit="gallon", price="25.00", stock=0)
    db_session.add(product)
    db_session.flush()

    stock_item = StockItem(name="Purified Water", unit="liter", quantity=Decimal("20"))
    db_session.add(stock_item)
    db_session.flush()

    ingredient = ProductIngredient(
        product_id=product.id, stock_item_id=stock_item.id, quantity=Decimal("4")
    )
    db_session.add(ingredient)
    db_session.commit()

    response = logged_in_client.get("/pos/")
    # available_stock = floor(20 / 4) = 5
    assert response.status_code == 200
    assert b"Out of stock" not in response.data
    assert b"gallon(s) left" in response.data


def test_pos_product_with_ingredients_zero_raw_stock_renders_out_of_stock(
    logged_in_client, db_session
):
    product = Product(name="Refill Gallon", unit="gallon", price="25.00", stock=0)
    db_session.add(product)
    db_session.flush()

    stock_item = StockItem(name="Purified Water", unit="liter", quantity=Decimal("0"))
    db_session.add(stock_item)
    db_session.flush()

    ingredient = ProductIngredient(
        product_id=product.id, stock_item_id=stock_item.id, quantity=Decimal("4")
    )
    db_session.add(ingredient)
    db_session.commit()

    response = logged_in_client.get("/pos/")
    # available_stock = floor(0 / 4) = 0
    assert response.status_code == 200
    assert b"Out of stock" in response.data
    assert b"disabled opacity-50" in response.data


def test_pos_save_with_custom_item_missing_name_flashes_error(logged_in_client):
    items = json.dumps([{"product_id": None, "name": "", "unit": "gallon", "price": "50.00", "quantity": "1"}])
    response = logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Custom item requires a name, unit, and price" in response.data


def test_pos_save_with_custom_item_zero_price_flashes_error(logged_in_client):
    items = json.dumps([{"product_id": None, "name": "Water", "unit": "gallon", "price": "0", "quantity": "1"}])
    response = logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Custom item requires a name, unit, and price" in response.data


def test_pos_save_with_invalid_payment_status_flashes_error(logged_in_client):
    response = logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "invalid_status",
            "amount_paid": "0",
            "items": json.dumps([{"product_id": 1, "quantity": "1"}]),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid payment status." in response.data


def test_pos_save_with_full_payment_sets_amount_paid_equal_to_total(
    logged_in_client, sample_product, db_session
):
    items = json.dumps([{"product_id": sample_product.id, "quantity": "3"}])
    logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",  # should be overridden to total
            "items": items,
        },
    )

    tx = Transaction.query.first()
    # 3 × 50.00 = 150.00
    expected_total = Decimal("3") * sample_product.price
    assert tx.total_amount == expected_total
    assert tx.amount_paid == tx.total_amount


def test_pos_save_with_unpaid_sets_amount_paid_to_zero(
    logged_in_client, sample_product, db_session
):
    items = json.dumps([{"product_id": sample_product.id, "quantity": "1"}])
    logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "unpaid",
            "amount_paid": "999",  # should be overridden to 0
            "items": items,
        },
    )

    tx = Transaction.query.first()
    assert tx.payment_status == "unpaid"
    assert tx.amount_paid == Decimal("0")


from app.models.product import Product


def test_pos_save_with_customer_id_links_transaction_to_customer(
    logged_in_client, sample_product, sample_customer, db_session
):
    items = json.dumps([{"product_id": sample_product.id, "quantity": "1"}])
    logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": str(sample_customer.id),
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
    )
    tx = Transaction.query.first()
    assert tx.customer_id == sample_customer.id


def test_pos_save_with_partial_payment_stores_correct_amount_paid(
    logged_in_client, sample_product, db_session
):
    items = json.dumps([{"product_id": sample_product.id, "quantity": "2"}])
    logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "partial",
            "amount_paid": "60.00",
            "items": items,
        },
    )
    tx = Transaction.query.first()
    assert tx.amount_paid == Decimal("60.00")
    assert tx.payment_status == "partial"


def test_pos_index_only_shows_active_products(
    logged_in_client, db_session, sample_product
):
    inactive = Product(name="Old Product", unit="gallon", price="10.00", is_active=False)
    db_session.add(inactive)
    db_session.commit()

    response = logged_in_client.get("/pos/")
    assert b"Water Gallon" in response.data
    assert b"Old Product" not in response.data


def test_pos_save_with_multiple_items_totals_correctly(
    logged_in_client, db_session, sample_product
):
    second_product = Product(name="Small Bottle", unit="bottle", price="15.00", stock=Decimal("100"))
    db_session.add(second_product)
    db_session.commit()

    items = json.dumps([
        {"product_id": sample_product.id, "quantity": "2"},
        {"product_id": second_product.id, "quantity": "3"},
    ])
    logged_in_client.post(
        "/pos/save",
        data={
            "customer_id": "",
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
    )
    tx = Transaction.query.first()
    assert tx.total_amount == Decimal("145.00")
    assert len(tx.items) == 2


def test_pos_index_renders_product_with_ingredients(logged_in_client, db_session):
    product = Product(
        name="Eagerly Loaded Gallon",
        unit="gallon",
        price="35.00",
        is_active=True,
        show_in_pos=True,
    )
    db_session.add(product)
    db_session.flush()

    stock_item = StockItem(name="Spring Water", unit="liter", quantity=Decimal("10"))
    db_session.add(stock_item)
    db_session.flush()

    ingredient = ProductIngredient(
        product_id=product.id, stock_item_id=stock_item.id, quantity=Decimal("2")
    )
    db_session.add(ingredient)
    db_session.commit()

    response = logged_in_client.get("/pos/")
    assert response.status_code == 200
    assert b"Eagerly Loaded Gallon" in response.data
