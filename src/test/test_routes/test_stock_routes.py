import json
from decimal import Decimal

import pytest

from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient
from app.models.transaction import Transaction


# ---------------------------------------------------------------------------
# GET /stock/
# ---------------------------------------------------------------------------


def test_stock_index_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/stock/")
    assert response.status_code == 200
    assert b"stock" in response.data.lower()


def test_stock_index_redirects_to_login_if_anonymous(client):
    response = client.get("/stock/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# POST /stock/add
# ---------------------------------------------------------------------------


def test_stock_add_creates_new_stock_item(logged_in_client, db_session):
    response = logged_in_client.post(
        "/stock/add",
        data={"name": "Rock Salt", "unit": "kg", "vendor_id": 0},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added" in response.data

    item = StockItem.query.filter_by(name="Rock Salt").first()
    assert item is not None
    assert item.unit == "kg"
    assert item.vendor_id is None


def test_stock_add_with_missing_name_flashes_error(logged_in_client, db_session):
    response = logged_in_client.post(
        "/stock/add",
        data={"name": "", "unit": "kg", "vendor_id": 0},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert StockItem.query.count() == 0


def test_stock_add_with_missing_unit_flashes_error(logged_in_client, db_session):
    response = logged_in_client.post(
        "/stock/add",
        data={"name": "Rock Salt", "unit": "", "vendor_id": 0},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert StockItem.query.count() == 0


def test_stock_add_requires_login(client):
    response = client.post(
        "/stock/add",
        data={"name": "Rock Salt", "unit": "kg", "vendor_id": 0},
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# POST /stock/<id>/adjust
# ---------------------------------------------------------------------------


def test_stock_adjust_increases_quantity(logged_in_client, sample_stock_item, db_session):
    item_id = sample_stock_item.id
    response = logged_in_client.post(
        f"/stock/{item_id}/adjust",
        data={"quantity": "15.5"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Added" in response.data

    db_session.refresh(sample_stock_item)
    # 20.0 + 15.5 = 35.5
    assert float(sample_stock_item.quantity) == pytest.approx(35.5)


def test_stock_adjust_nonexistent_item_returns_404(logged_in_client):
    response = logged_in_client.post(
        "/stock/99999/adjust",
        data={"quantity": "5"},
    )
    assert response.status_code == 404


def test_stock_adjust_with_zero_quantity_flashes_error(
    logged_in_client, sample_stock_item, db_session
):
    item_id = sample_stock_item.id
    response = logged_in_client.post(
        f"/stock/{item_id}/adjust",
        data={"quantity": "0"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    db_session.refresh(sample_stock_item)
    assert float(sample_stock_item.quantity) == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# POST /stock/<id>/delete
# ---------------------------------------------------------------------------


def test_stock_delete_succeeds_when_item_has_no_ingredients(
    logged_in_client, sample_stock_item, db_session
):
    item_id = sample_stock_item.id
    response = logged_in_client.post(
        f"/stock/{item_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"removed" in response.data

    assert db_session.get(StockItem, item_id) is None


def test_stock_delete_blocked_when_item_is_used_as_ingredient(
    logged_in_client, sample_stock_item, db_session
):
    product = Product(name="Ingredient Consumer", unit="unit", price="10.00")
    db_session.add(product)
    db_session.flush()

    ing = ProductIngredient(
        product_id=product.id,
        stock_item_id=sample_stock_item.id,
        quantity=Decimal("1"),
    )
    db_session.add(ing)
    db_session.commit()

    response = logged_in_client.post(
        f"/stock/{sample_stock_item.id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Cannot delete" in response.data

    assert db_session.get(StockItem, sample_stock_item.id) is not None


def test_stock_delete_nonexistent_item_returns_404(logged_in_client):
    response = logged_in_client.post("/stock/99999/delete")
    assert response.status_code == 404


def test_stock_edit_with_blank_name_flashes_error(logged_in_client, sample_stock_item, db_session):
    item_id = sample_stock_item.id
    response = logged_in_client.post(
        f"/stock/{item_id}/edit",
        data={"name": "", "unit": "liter", "vendor_id": 0},
        follow_redirects=True,
    )
    assert response.status_code == 200

    db_session.refresh(sample_stock_item)
    assert sample_stock_item.name == "Purified Water"


def test_stock_edit_updates_stock_item(logged_in_client, sample_stock_item, db_session):
    item_id = sample_stock_item.id
    response = logged_in_client.post(
        f"/stock/{item_id}/edit",
        data={"name": "Filtered Water", "unit": "liter", "vendor_id": 0},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"updated" in response.data

    db_session.refresh(sample_stock_item)
    assert sample_stock_item.name == "Filtered Water"


def test_stock_edit_with_blank_unit_flashes_error(logged_in_client, sample_stock_item, db_session):
    item_id = sample_stock_item.id
    response = logged_in_client.post(
        f"/stock/{item_id}/edit",
        data={"name": "Purified Water", "unit": "", "vendor_id": 0},
        follow_redirects=True,
    )
    assert response.status_code == 200

    db_session.refresh(sample_stock_item)
    assert sample_stock_item.unit == "liter"


# ---------------------------------------------------------------------------
# GET /stock/restock
# ---------------------------------------------------------------------------


def test_stock_restock_index_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/stock/restock")
    assert response.status_code == 200


def test_stock_restock_index_redirects_to_login_if_anonymous(client):
    response = client.get("/stock/restock")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# POST /stock/restock/save
# ---------------------------------------------------------------------------


def test_stock_restock_save_increments_stock_item_and_redirects(
    logged_in_client, sample_vendor, sample_stock_item, db_session
):
    items = json.dumps([
        {"stock_item_id": sample_stock_item.id, "quantity": "10", "unit_price": "3.00"}
    ])
    response = logged_in_client.post(
        "/stock/restock/save",
        data={
            "items": items,
            "vendor_id": str(sample_vendor.id),
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"saved" in response.data

    db_session.refresh(sample_stock_item)
    assert float(sample_stock_item.quantity) == pytest.approx(30.0)  # 20 + 10

    tx = Transaction.query.filter_by(transaction_type="stock_restock").first()
    assert tx is not None
    assert tx.vendor_id == sample_vendor.id


def test_stock_restock_save_with_empty_cart_flashes_error(
    logged_in_client, sample_vendor
):
    response = logged_in_client.post(
        "/stock/restock/save",
        data={
            "items": json.dumps([]),
            "vendor_id": str(sample_vendor.id),
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Cart is empty" in response.data


def test_stock_restock_save_with_nonexistent_vendor_flashes_error(
    logged_in_client, sample_stock_item
):
    items = json.dumps([
        {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "2.00"}
    ])
    response = logged_in_client.post(
        "/stock/restock/save",
        data={
            "items": items,
            "vendor_id": "99999",
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Vendor not found" in response.data


def test_stock_restock_save_with_missing_vendor_flashes_error(
    logged_in_client, sample_stock_item
):
    items = json.dumps([
        {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "2.00"}
    ])
    response = logged_in_client.post(
        "/stock/restock/save",
        data={
            "items": items,
            "vendor_id": "",
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"vendor" in response.data.lower()


def test_stock_restock_save_requires_login(client, sample_vendor, sample_stock_item):
    items = json.dumps([
        {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "2.00"}
    ])
    response = client.post(
        "/stock/restock/save",
        data={
            "items": items,
            "vendor_id": str(sample_vendor.id),
            "payment_status": "full",
            "amount_paid": "0",
        },
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_stock_restock_save_stores_unit_price_snapshot_on_transaction_item(
    logged_in_client, sample_vendor, sample_stock_item, db_session
):
    # The frontend computes unit_price = totalPrice / qty before submitting.
    # Verify that the submitted unit_price — not total_price — ends up as
    # unit_price_snapshot on the persisted TransactionItem.
    items = json.dumps([
        {"stock_item_id": sample_stock_item.id, "quantity": "5", "unit_price": "12.50"}
    ])
    response = logged_in_client.post(
        "/stock/restock/save",
        data={
            "items": items,
            "vendor_id": str(sample_vendor.id),
            "payment_status": "full",
            "amount_paid": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    tx = Transaction.query.filter_by(transaction_type="stock_restock").first()
    assert tx is not None
    assert len(tx.items) == 1
    assert tx.items[0].unit_price_snapshot == Decimal("12.50")
    assert tx.items[0].quantity == Decimal("5")
    # total = unit_price * qty = 12.50 * 5 = 62.50
    assert tx.total_amount == Decimal("62.50")
