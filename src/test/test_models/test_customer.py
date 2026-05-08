import pytest
from sqlalchemy.exc import IntegrityError

from app.models.customer import Customer
from app.models.transaction import Transaction


def test_customer_can_be_created_with_name(db_session):
    customer = Customer(name="Maria Santos")
    db_session.add(customer)
    db_session.commit()

    saved = db_session.get(Customer, customer.id)
    assert saved is not None
    assert saved.name == "Maria Santos"


def test_created_at_is_set_automatically(db_session):
    customer = Customer(name="Date Check")
    db_session.add(customer)
    db_session.commit()

    assert customer.created_at is not None


def test_customer_can_have_multiple_transactions(db_session):
    customer = Customer(name="Multi Buyer")
    db_session.add(customer)
    db_session.flush()

    tx1 = Transaction(
        customer_id=customer.id,
        transaction_type="sale",
        total_amount="50.00",
        amount_paid="50.00",
        payment_status="full",
    )
    tx2 = Transaction(
        customer_id=customer.id,
        transaction_type="sale",
        total_amount="30.00",
        amount_paid="0.00",
        payment_status="unpaid",
    )
    db_session.add_all([tx1, tx2])
    db_session.commit()

    # Re-fetch to get a fresh instance with the relationship loaded.
    saved = db_session.get(Customer, customer.id)
    assert len(saved.transactions) == 2


def test_name_cannot_be_null(db_session):
    customer = Customer(name=None)
    db_session.add(customer)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
