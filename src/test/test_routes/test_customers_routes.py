from app.models.customer import Customer
from app.models.transaction import Transaction


def test_customers_index_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/customers/")
    assert response.status_code == 200


def test_customers_add_creates_customer(logged_in_client, db_session):
    response = logged_in_client.post(
        "/customers/add",
        data={"name": "Pedro Reyes"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added" in response.data

    customer = Customer.query.filter_by(name="Pedro Reyes").first()
    assert customer is not None


def test_customers_add_with_empty_name_flashes_error(logged_in_client, db_session):
    response = logged_in_client.post(
        "/customers/add",
        data={"name": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"required" in response.data

    assert Customer.query.count() == 0


def test_customers_edit_updates_name(logged_in_client, sample_customer, db_session):
    customer_id = sample_customer.id
    response = logged_in_client.post(
        f"/customers/{customer_id}/edit",
        data={"name": "Juan Reyes"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"updated" in response.data

    updated = db_session.get(Customer, customer_id)
    assert updated.name == "Juan Reyes"


def test_customers_delete_removes_customer_from_db(
    logged_in_client, sample_customer, db_session
):
    customer_id = sample_customer.id
    response = logged_in_client.post(
        f"/customers/{customer_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"removed" in response.data

    assert db_session.get(Customer, customer_id) is None


def test_customers_edit_with_empty_name_flashes_error(
    logged_in_client, sample_customer, db_session
):
    customer_id = sample_customer.id
    response = logged_in_client.post(
        f"/customers/{customer_id}/edit",
        data={"name": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"required" in response.data

    unchanged = db_session.get(Customer, customer_id)
    assert unchanged.name == "Juan dela Cruz"


def test_customers_edit_nonexistent_customer_returns_404(logged_in_client):
    response = logged_in_client.post(
        "/customers/99999/edit",
        data={"name": "Ghost"},
    )
    assert response.status_code == 404


def test_customers_delete_nonexistent_customer_returns_404(logged_in_client):
    response = logged_in_client.post("/customers/99999/delete")
    assert response.status_code == 404


def test_customers_delete_with_linked_transaction_flashes_error(
    logged_in_client, sample_customer, db_session
):
    tx = Transaction(
        customer_id=sample_customer.id,
        transaction_type="sale",
        total_amount="0.00",
    )
    db_session.add(tx)
    db_session.commit()

    customer_id = sample_customer.id
    response = logged_in_client.post(
        f"/customers/{customer_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Cannot delete" in response.data
    assert sample_customer.name.encode() in response.data

    assert db_session.get(Customer, customer_id) is not None
