import pytest
from sqlalchemy.exc import IntegrityError

from app.models.transaction import Transaction, TransactionItem


def test_transaction_can_be_created_with_items(db_session, sample_product):
    tx = Transaction(
        customer_id=None,
        transaction_type="sale",
        total_amount="100.00",
        amount_paid="100.00",
        payment_status="full",
    )
    db_session.add(tx)
    db_session.flush()

    item = TransactionItem(
        transaction_id=tx.id,
        product_id=sample_product.id,
        product_name_snapshot="Water Gallon",
        unit_snapshot="gallon",
        unit_price_snapshot="50.00",
        quantity="2",
        subtotal="100.00",
    )
    db_session.add(item)
    db_session.commit()

    saved_tx = db_session.get(Transaction, tx.id)
    assert saved_tx is not None
    assert len(saved_tx.items) == 1
    assert saved_tx.items[0].product_name_snapshot == "Water Gallon"


def test_transaction_item_cascade_deletes_with_parent(db_session, sample_transaction):
    tx_id = sample_transaction.id
    item_id = sample_transaction.items[0].id

    db_session.delete(sample_transaction)
    db_session.commit()

    assert db_session.get(Transaction, tx_id) is None
    assert db_session.get(TransactionItem, item_id) is None


def test_customer_id_is_nullable(db_session):
    tx = Transaction(
        customer_id=None,
        transaction_type="sale",
        total_amount="75.00",
        amount_paid="75.00",
        payment_status="full",
    )
    db_session.add(tx)
    db_session.commit()

    saved = db_session.get(Transaction, tx.id)
    assert saved.customer_id is None


def test_transaction_created_at_is_set_automatically(db_session):
    tx = Transaction(
        customer_id=None,
        transaction_type="sale",
        total_amount="20.00",
        amount_paid="20.00",
        payment_status="full",
    )
    db_session.add(tx)
    db_session.commit()

    saved = db_session.get(Transaction, tx.id)
    assert saved.created_at is not None


def test_transaction_item_product_name_snapshot_cannot_be_null(db_session, sample_product):
    tx = Transaction(
        customer_id=None,
        transaction_type="sale",
        total_amount="10.00",
        amount_paid="10.00",
        payment_status="full",
    )
    db_session.add(tx)
    db_session.flush()

    item = TransactionItem(
        transaction_id=tx.id,
        product_id=sample_product.id,
        product_name_snapshot=None,
        unit_snapshot="pcs",
        unit_price_snapshot="10.00",
        quantity="1",
        subtotal="10.00",
    )
    db_session.add(item)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_transaction_rejects_unknown_transaction_type():
    with pytest.raises(ValueError, match="Invalid transaction_type"):
        Transaction(
            transaction_type="refund",
            total_amount="50.00",
            amount_paid="50.00",
            payment_status="full",
        )


def test_transaction_accepts_all_valid_types(db_session):
    for tx_type in Transaction.VALID_TYPES:
        tx = Transaction(
            transaction_type=tx_type,
            total_amount="10.00",
            amount_paid="10.00",
            payment_status="full",
        )
        db_session.add(tx)
    db_session.commit()  # all three must persist without error
