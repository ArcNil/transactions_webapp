import json

from app.models.transaction import Transaction


def test_transactions_index_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/transactions/")
    assert response.status_code == 200


def test_transactions_index_redirects_to_login_if_anonymous(client):
    response = client.get("/transactions/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_transactions_edit_with_empty_items_list_flashes_warning(
    logged_in_client, sample_transaction
):
    tx_id = sample_transaction.id
    response = logged_in_client.post(
        f"/transactions/{tx_id}/edit",
        data={
            "payment_status": "full",
            "amount_paid": "0",
            "items": json.dumps([]),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"A transaction must have at least one item." in response.data


def test_transactions_edit_nonexistent_transaction_returns_404(logged_in_client):
    response = logged_in_client.post(
        "/transactions/99999/edit",
        data={
            "payment_status": "full",
            "amount_paid": "0",
            "items": json.dumps([{"product_id": 1, "quantity": "1"}]),
        },
    )
    assert response.status_code == 404


def test_transactions_edit_with_malformed_json_items_flashes_error(
    logged_in_client, sample_transaction
):
    tx_id = sample_transaction.id
    response = logged_in_client.post(
        f"/transactions/{tx_id}/edit",
        data={
            "payment_status": "full",
            "amount_paid": "0",
            "items": "not-valid-json",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid item data." in response.data


from decimal import Decimal

from app.models.product import Product


def test_transactions_edit_recalculates_total_amount_after_quantity_change(
    logged_in_client, sample_transaction, db_session
):
    tx_id = sample_transaction.id
    item_id = sample_transaction.items[0].id

    logged_in_client.post(
        f"/transactions/{tx_id}/edit",
        data={
            "payment_status": "full",
            "amount_paid": "0",
            "items": json.dumps([{"item_id": item_id, "quantity": "4"}]),
        },
        follow_redirects=True,
    )
    db_session.refresh(sample_transaction)
    assert sample_transaction.total_amount == Decimal("200.00")


def test_transactions_edit_updates_customer_id(
    logged_in_client, sample_transaction, sample_customer, db_session
):
    tx_id = sample_transaction.id
    item_id = sample_transaction.items[0].id

    logged_in_client.post(
        f"/transactions/{tx_id}/edit",
        data={
            "customer_id": str(sample_customer.id),
            "payment_status": "full",
            "amount_paid": "0",
            "items": json.dumps([{"item_id": item_id, "quantity": "2"}]),
        },
        follow_redirects=True,
    )
    db_session.refresh(sample_transaction)
    assert sample_transaction.customer_id == sample_customer.id


def test_transactions_edit_adds_new_item_to_transaction(
    logged_in_client, sample_transaction, db_session
):
    new_product = Product(name="Mineral Water", unit="bottle", price="20.00")
    db_session.add(new_product)
    db_session.commit()

    tx_id = sample_transaction.id
    item_id = sample_transaction.items[0].id
    items = json.dumps([
        {"item_id": item_id, "quantity": "2"},
        {"product_id": new_product.id, "quantity": "1"},
    ])
    logged_in_client.post(
        f"/transactions/{tx_id}/edit",
        data={
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
        follow_redirects=True,
    )
    db_session.refresh(sample_transaction)
    assert len(sample_transaction.items) == 2


def test_transactions_edit_removes_item_omitted_from_submission(
    logged_in_client, sample_transaction, db_session
):
    new_product = Product(name="Sparkling Water", unit="can", price="30.00")
    db_session.add(new_product)
    db_session.commit()

    tx_id = sample_transaction.id
    items = json.dumps([{"product_id": new_product.id, "quantity": "1"}])
    logged_in_client.post(
        f"/transactions/{tx_id}/edit",
        data={
            "payment_status": "full",
            "amount_paid": "0",
            "items": items,
        },
        follow_redirects=True,
    )
    db_session.refresh(sample_transaction)
    assert len(sample_transaction.items) == 1
    assert sample_transaction.items[0].product_id == new_product.id


def test_transactions_edit_non_sale_transaction_returns_403(logged_in_client, db_session):
    tx = Transaction(
        transaction_type="restock",
        total_amount="100.00",
    )
    db_session.add(tx)
    db_session.commit()

    response = logged_in_client.post(
        f"/transactions/{tx.id}/edit",
        data={
            "payment_status": "full",
            "amount_paid": "100.00",
            "items": json.dumps([]),
        },
    )
    assert response.status_code == 403
