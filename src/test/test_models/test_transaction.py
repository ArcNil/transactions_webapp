import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.models.transaction import Transaction, TransactionItem, TransactionLedgerEntry


# ---------------------------------------------------------------------------
# Transaction — core column behaviour
# ---------------------------------------------------------------------------


def test_transaction_can_be_created_with_items(db_session, sample_product):
    tx = Transaction(
        customer_id=None,
        transaction_type="sale",
        total_amount="100.00",
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
        )


def test_transaction_accepts_all_valid_types(db_session):
    for tx_type in Transaction.VALID_TYPES:
        tx = Transaction(
            transaction_type=tx_type,
            total_amount="10.00",
        )
        db_session.add(tx)
    db_session.commit()


# ---------------------------------------------------------------------------
# Transaction — closed_at / is_closed
# ---------------------------------------------------------------------------


def test_closed_at_is_null_by_default(db_session):
    tx = Transaction(transaction_type="sale", total_amount="30.00")
    db_session.add(tx)
    db_session.commit()

    saved = db_session.get(Transaction, tx.id)
    assert saved.closed_at is None


def test_is_closed_false_when_closed_at_is_none(db_session):
    tx = Transaction(transaction_type="sale", total_amount="30.00")
    db_session.add(tx)
    db_session.commit()

    assert tx.is_closed is False


def test_is_closed_true_when_closed_at_is_set(db_session):
    tx = Transaction(
        transaction_type="sale",
        total_amount="30.00",
        closed_at=datetime.now(timezone.utc),
    )
    db_session.add(tx)
    db_session.commit()

    assert tx.is_closed is True


# ---------------------------------------------------------------------------
# TransactionLedgerEntry — core column behaviour
# ---------------------------------------------------------------------------


def test_ledger_entry_can_be_created_with_valid_type(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    entry = TransactionLedgerEntry(
        transaction_id=tx.id,
        entry_type="payment",
        amount="50.00",
    )
    db_session.add(entry)
    db_session.commit()

    saved = db_session.get(TransactionLedgerEntry, entry.id)
    assert saved is not None
    assert saved.entry_type == "payment"
    assert saved.amount == Decimal("50.00")


def test_ledger_entry_rejects_invalid_entry_type():
    with pytest.raises(ValueError, match="Invalid entry_type"):
        TransactionLedgerEntry(
            transaction_id=1,
            entry_type="unknown",
            amount="10.00",
        )


def test_ledger_entry_accepts_all_valid_types(db_session):
    tx = Transaction(transaction_type="sale", total_amount="10.00")
    db_session.add(tx)
    db_session.flush()

    for entry_type in TransactionLedgerEntry.VALID_TYPES:
        entry = TransactionLedgerEntry(
            transaction_id=tx.id,
            entry_type=entry_type,
            amount="1.00",
        )
        db_session.add(entry)
    db_session.commit()


def test_ledger_entry_created_at_is_set_automatically(db_session):
    tx = Transaction(transaction_type="sale", total_amount="20.00")
    db_session.add(tx)
    db_session.flush()

    entry = TransactionLedgerEntry(
        transaction_id=tx.id,
        entry_type="payment",
        amount="20.00",
    )
    db_session.add(entry)
    db_session.commit()

    saved = db_session.get(TransactionLedgerEntry, entry.id)
    assert saved.created_at is not None


def test_ledger_entry_note_is_nullable(db_session):
    tx = Transaction(transaction_type="sale", total_amount="10.00")
    db_session.add(tx)
    db_session.flush()

    entry = TransactionLedgerEntry(
        transaction_id=tx.id,
        entry_type="payment",
        amount="10.00",
        note=None,
    )
    db_session.add(entry)
    db_session.commit()

    saved = db_session.get(TransactionLedgerEntry, entry.id)
    assert saved.note is None


def test_ledger_entries_cascade_delete_with_parent_transaction(db_session):
    tx = Transaction(transaction_type="sale", total_amount="40.00")
    db_session.add(tx)
    db_session.flush()

    entry = TransactionLedgerEntry(
        transaction_id=tx.id,
        entry_type="payment",
        amount="40.00",
    )
    db_session.add(entry)
    db_session.commit()

    entry_id = entry.id
    db_session.delete(tx)
    db_session.commit()

    assert db_session.get(TransactionLedgerEntry, entry_id) is None


# ---------------------------------------------------------------------------
# Transaction — derived properties: total_paid
# ---------------------------------------------------------------------------


def test_total_paid_is_zero_with_no_entries(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.commit()

    assert tx.total_paid == Decimal("0")


def test_total_paid_sums_payment_entries(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    for amount in ("20.00", "30.00"):
        db_session.add(TransactionLedgerEntry(
            transaction_id=tx.id, entry_type="payment", amount=amount,
        ))
    db_session.commit()

    assert tx.total_paid == Decimal("50.00")


def test_total_paid_excludes_non_payment_entries(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="50.00",
    ))
    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="change", amount="10.00",
    ))
    db_session.commit()

    assert tx.total_paid == Decimal("50.00")


# ---------------------------------------------------------------------------
# Transaction — derived properties: total_returned
# ---------------------------------------------------------------------------


def test_total_returned_is_zero_with_no_entries(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.commit()

    assert tx.total_returned == Decimal("0")


def test_total_returned_sums_change_refund_discount(db_session):
    tx = Transaction(transaction_type="sale", total_amount="100.00")
    db_session.add(tx)
    db_session.flush()

    for entry_type, amount in [("change", "5.00"), ("refund", "3.00"), ("discount", "2.00")]:
        db_session.add(TransactionLedgerEntry(
            transaction_id=tx.id, entry_type=entry_type, amount=amount,
        ))
    db_session.commit()

    assert tx.total_returned == Decimal("10.00")


def test_total_returned_excludes_adjustment_and_payment(db_session):
    tx = Transaction(transaction_type="sale", total_amount="100.00")
    db_session.add(tx)
    db_session.flush()

    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="adjustment", amount="5.00",
    ))
    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="100.00",
    ))
    db_session.commit()

    assert tx.total_returned == Decimal("0")


# ---------------------------------------------------------------------------
# Transaction — derived properties: balance
# ---------------------------------------------------------------------------


def test_balance_is_negative_when_underpaid(db_session):
    tx = Transaction(transaction_type="sale", total_amount="100.00")
    db_session.add(tx)
    db_session.flush()

    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="60.00",
    ))
    db_session.commit()

    assert tx.balance == Decimal("-40.00")


def test_balance_is_zero_when_settled(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="50.00",
    ))
    db_session.commit()

    assert tx.balance == Decimal("0")


def test_balance_is_positive_when_overpaid(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="70.00",
    ))
    db_session.commit()

    assert tx.balance == Decimal("20.00")


def test_balance_accounts_for_returned_amounts(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    # paid 60, gave 10 change → net paid 50 → balance = 0
    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="60.00",
    ))
    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="change", amount="10.00",
    ))
    db_session.commit()

    assert tx.balance == Decimal("0")


def test_balance_accounts_for_positive_adjustment(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    # paid 40, positive adjustment of 10 → net = 40 + 10 - 50 = 0
    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="40.00",
    ))
    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="adjustment", amount="10.00",
    ))
    db_session.commit()

    assert tx.balance == Decimal("0")


# ---------------------------------------------------------------------------
# Transaction — derived properties: effective_status
# ---------------------------------------------------------------------------


def test_effective_status_is_closed_when_closed_at_set(db_session):
    tx = Transaction(
        transaction_type="sale",
        total_amount="50.00",
        closed_at=datetime.now(timezone.utc),
    )
    db_session.add(tx)
    db_session.commit()

    assert tx.effective_status == "Closed"


def test_effective_status_is_balance_owed_when_underpaid(db_session):
    tx = Transaction(transaction_type="sale", total_amount="100.00")
    db_session.add(tx)
    db_session.flush()

    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="60.00",
    ))
    db_session.commit()

    assert tx.effective_status == "Balance owed"


def test_effective_status_is_settled_when_balance_zero(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="50.00",
    ))
    db_session.commit()

    assert tx.effective_status == "Settled"


def test_effective_status_is_overpaid_when_balance_positive(db_session):
    tx = Transaction(transaction_type="sale", total_amount="50.00")
    db_session.add(tx)
    db_session.flush()

    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="70.00",
    ))
    db_session.commit()

    assert tx.effective_status == "Overpaid"


def test_effective_status_closed_takes_priority_over_balance(db_session):
    """A closed transaction reports 'Closed' even when balance != 0."""
    tx = Transaction(
        transaction_type="sale",
        total_amount="100.00",
        closed_at=datetime.now(timezone.utc),
    )
    db_session.add(tx)
    db_session.flush()

    # underpaid but closed
    db_session.add(TransactionLedgerEntry(
        transaction_id=tx.id, entry_type="payment", amount="40.00",
    ))
    db_session.commit()

    assert tx.effective_status == "Closed"
