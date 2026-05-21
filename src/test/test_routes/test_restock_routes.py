import json
from decimal import Decimal

import pytest

from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient
from app.models.transaction import Transaction
from app.models.vendor import Vendor


@pytest.fixture
def restock_product(db_session):
    """Product with a vendor and one ProductIngredient, usable in restock cart payloads."""
    vendor = Vendor(name="Restock Test Vendor")
    stock_item = StockItem(name="Raw Water", unit="liter", quantity=Decimal("0"))
    db_session.add_all([vendor, stock_item])
    db_session.flush()
    product = Product(
        name="Water Delivery",
        unit="delivery",
        price="200.00",
        stock=Decimal("0"),
        vendor_id=vendor.id,
        product_type="purchase",
    )
    db_session.add(product)
    db_session.flush()
    ing = ProductIngredient(
        product_id=product.id,
        stock_item_id=stock_item.id,
        quantity=Decimal("1000"),
    )
    db_session.add(ing)
    db_session.commit()
    return product


# ---------------------------------------------------------------------------
# GET /restock/
# ---------------------------------------------------------------------------


def test_restock_index_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/restock/")
    assert response.status_code == 200
    assert b"restock" in response.data.lower()


def test_restock_index_redirects_to_login_if_anonymous(client):
    response = client.get("/restock/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_restock_index_passes_vendor_products_to_template(
    logged_in_client, restock_product
):
    response = logged_in_client.get("/restock/")
    assert response.status_code == 200
    assert restock_product.name.encode() in response.data


def test_restock_index_excludes_purchase_products_without_vendor(
    logged_in_client, db_session
):
    product = Product(
        name="No Vendor Item",
        unit="unit",
        price="10.00",
        product_type="purchase",
    )
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/restock/")
    assert response.status_code == 200
    assert b"No Vendor Item" not in response.data


def test_restock_index_shows_no_vendor_count_warning(
    logged_in_client, db_session
):
    product = Product(
        name="Unassigned Purchase",
        unit="unit",
        price="5.00",
        product_type="purchase",
    )
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/restock/")
    assert response.status_code == 200
    assert b"1 product" in response.data
    assert b"no vendor assigned" in response.data.lower()


# ---------------------------------------------------------------------------
# POST /restock/save — happy path
# ---------------------------------------------------------------------------


def test_restock_save_creates_transaction_and_flashes_success(
    logged_in_client, restock_product, db_session
):
    items = json.dumps(
        [
            {
                "product_id": restock_product.id,
                "quantity": "1",
                "unit_price": "200",
            }
        ]
    )
    response = logged_in_client.post(
        "/restock/save",
        data={
            "items": items,
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Restock saved!" in response.data

    tx = Transaction.query.filter_by(transaction_type="product_restock").first()
    assert tx is not None


# ---------------------------------------------------------------------------
# POST /restock/save — TransactionError paths
# ---------------------------------------------------------------------------


def test_restock_save_with_empty_cart_flashes_error(logged_in_client):
    response = logged_in_client.post(
        "/restock/save",
        data={
            "items": "[]",
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Cart is empty." in response.data


def test_restock_save_with_invalid_json_flashes_error(logged_in_client):
    response = logged_in_client.post(
        "/restock/save",
        data={
            "items": "not-json",
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid cart data." in response.data


def test_restock_save_with_item_missing_product_id_flashes_error(logged_in_client):
    items = json.dumps([{"quantity": "1", "unit_price": "5"}])
    response = logged_in_client.post(
        "/restock/save",
        data={
            "items": items,
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid item data." in response.data


def test_restock_save_with_unknown_product_id_flashes_error(logged_in_client):
    items = json.dumps(
        [{"product_id": 99999, "quantity": "1", "unit_price": "5"}]
    )
    response = logged_in_client.post(
        "/restock/save",
        data={
            "items": items,
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"not found" in response.data.lower()


def test_restock_save_with_zero_quantity_flashes_error(
    logged_in_client, restock_product
):
    items = json.dumps(
        [{"product_id": restock_product.id, "quantity": "0", "unit_price": "5"}]
    )
    response = logged_in_client.post(
        "/restock/save",
        data={
            "items": items,
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Quantity must be" in response.data


def test_restock_save_requires_login(client):
    response = client.post(
        "/restock/save",
        data={
            "items": "[]",
            "payment_status": "full",
            "amount_paid": "0",
        },
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# GET /restock/ — product filtering edge cases
# ---------------------------------------------------------------------------


def test_restock_index_excludes_sale_type_products(logged_in_client, db_session):
    from app.models.vendor import Vendor

    vendor = Vendor(name="Sale Type Vendor")
    db_session.add(vendor)
    db_session.flush()
    product = Product(
        name="Sale Only Item",
        unit="unit",
        price="10.00",
        product_type="sale",
        vendor_id=vendor.id,
    )
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/restock/")
    assert response.status_code == 200
    assert b"Sale Only Item" not in response.data


def test_restock_save_with_mixed_vendor_cart_flashes_error(
    logged_in_client, db_session
):
    from app.models.vendor import Vendor

    vendor1 = Vendor(name="Vendor Alpha")
    vendor2 = Vendor(name="Vendor Beta")
    db_session.add_all([vendor1, vendor2])
    db_session.flush()
    p1 = Product(
        name="Alpha Product",
        unit="unit",
        price="10.00",
        product_type="purchase",
        vendor_id=vendor1.id,
    )
    p2 = Product(
        name="Beta Product",
        unit="unit",
        price="20.00",
        product_type="purchase",
        vendor_id=vendor2.id,
    )
    db_session.add_all([p1, p2])
    db_session.commit()

    items = json.dumps([
        {"product_id": p1.id, "quantity": "1", "unit_price": "10"},
        {"product_id": p2.id, "quantity": "1", "unit_price": "20"},
    ])
    response = logged_in_client.post(
        "/restock/save",
        data={"items": items, "payment_status": "full", "amount_paid": "0"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"single vendor" in response.data
