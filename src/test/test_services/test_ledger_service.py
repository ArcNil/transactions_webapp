import pytest
from decimal import Decimal

from app.models.transaction import Transaction, TransactionLedgerEntry
from app.services.ledger_service import (
    LedgerError,
    add_entry,
    update_entry,
    delete_entry,
    close_transaction,
    reopen_transaction,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _open_tx(db_session, total="50.00"):
    tx = Transaction(transaction_type="sale", total_amount=total)
    db_session.add(tx)
    db_session.flush()
    return tx


# ---------------------------------------------------------------------------
# add_entry
# ---------------------------------------------------------------------------


def test_add_entry_creates_payment_entry(db_session):
    tx = _open_tx(db_session)
    entry = add_entry(tx, "payment", "30.00")

    assert entry.id is not None
    assert entry.transaction_id == tx.id
    assert entry.entry_type == "payment"
    assert entry.amount == Decimal("30.00")
    assert entry.note is None


def test_add_entry_creates_change_entry(db_session):
    tx = _open_tx(db_session)
    entry = add_entry(tx, "change", "5.00")

    assert entry.entry_type == "change"
    assert entry.amount == Decimal("5.00")


def test_add_entry_creates_adjustment_entry_with_negative_amount(db_session):
    tx = _open_tx(db_session)
    entry = add_entry(tx, "adjustment", "-10.00")

    assert entry.entry_type == "adjustment"
    assert entry.amount == Decimal("-10.00")


def test_add_entry_raises_for_invalid_entry_type(db_session):
    tx = _open_tx(db_session)

    with pytest.raises(LedgerError, match="Invalid entry type"):
        add_entry(tx, "bribe", "10.00")


def test_add_entry_raises_for_invalid_amount(db_session):
    tx = _open_tx(db_session)

    with pytest.raises(LedgerError, match="Invalid amount"):
        add_entry(tx, "payment", "not-a-number")


def test_add_entry_raises_for_negative_amount_on_non_adjustment_type(db_session):
    tx = _open_tx(db_session)

    with pytest.raises(LedgerError, match="zero or greater"):
        add_entry(tx, "payment", "-10.00")


def test_add_entry_raises_when_tx_is_closed(db_session):
    tx = _open_tx(db_session)
    close_transaction(tx)

    with pytest.raises(LedgerError, match="closed"):
        add_entry(tx, "payment", "10.00")


def test_add_entry_auto_closes_tx_when_balance_reaches_zero(db_session):
    tx = _open_tx(db_session, total="50.00")
    add_entry(tx, "payment", "50.00")

    db_session.refresh(tx)
    assert tx.is_closed
    assert tx.closed_at is not None
    assert tx.balance == Decimal("0")


def test_add_entry_does_not_auto_close_when_balance_still_negative(db_session):
    tx = _open_tx(db_session, total="50.00")
    add_entry(tx, "payment", "30.00")

    db_session.refresh(tx)
    assert not tx.is_closed
    assert tx.balance == Decimal("-20.00")


def test_add_entry_strips_and_truncates_note(db_session):
    tx = _open_tx(db_session)
    long_note = "  " + ("x" * 300) + "  "
    entry = add_entry(tx, "payment", "10.00", note=long_note)

    assert len(entry.note) == 255
    assert not entry.note.startswith(" ")


# ---------------------------------------------------------------------------
# update_entry
# ---------------------------------------------------------------------------


def test_update_entry_persists_updated_amount_and_note(db_session):
    tx = _open_tx(db_session, total="50.00")
    entry = add_entry(tx, "payment", "30.00", note="initial")

    updated = update_entry(entry, "payment", "40.00", note="revised")

    assert updated.amount == Decimal("40.00")
    assert updated.note == "revised"
    assert updated.entry_type == "payment"


def test_update_entry_raises_when_tx_is_closed(db_session):
    tx = _open_tx(db_session, total="50.00")
    entry = add_entry(tx, "payment", "30.00")
    close_transaction(tx)

    with pytest.raises(LedgerError, match="closed"):
        update_entry(entry, "payment", "35.00")


def test_update_entry_raises_for_invalid_entry_type(db_session):
    tx = _open_tx(db_session, total="50.00")
    entry = add_entry(tx, "payment", "30.00")

    with pytest.raises(LedgerError, match="Invalid entry type"):
        update_entry(entry, "coupon", "30.00")


def test_update_entry_auto_closes_tx_when_balance_reaches_zero(db_session):
    tx = _open_tx(db_session, total="50.00")
    entry = add_entry(tx, "payment", "30.00")

    db_session.refresh(tx)
    assert not tx.is_closed

    update_entry(entry, "payment", "50.00")

    db_session.refresh(tx)
    assert tx.is_closed
    assert tx.balance == Decimal("0")


def test_update_entry_keeps_tx_open_when_edit_leaves_balance_nonzero(db_session):
    """
    Settle a tx via auto-close, reopen it manually, then edit the payment
    down so balance is no longer zero — tx must remain open.
    """
    tx = _open_tx(db_session, total="50.00")
    # Payment of 50 settles the tx and triggers auto-close.
    entry = add_entry(tx, "payment", "50.00")
    db_session.refresh(tx)
    assert tx.is_closed

    # Reopen so we can edit.
    reopen_transaction(tx)
    db_session.refresh(tx)
    assert not tx.is_closed

    # Reduce the payment — balance becomes -20, so tx should NOT be closed.
    update_entry(entry, "payment", "30.00")

    db_session.refresh(tx)
    assert not tx.is_closed
    assert tx.balance == Decimal("-20.00")


# ---------------------------------------------------------------------------
# delete_entry
# ---------------------------------------------------------------------------


def test_delete_entry_removes_entry_from_open_tx(db_session):
    tx = _open_tx(db_session, total="50.00")
    entry = add_entry(tx, "payment", "30.00")
    entry_id = entry.id

    delete_entry(entry)

    db_session.refresh(tx)
    remaining_ids = [e.id for e in tx.ledger_entries]
    assert entry_id not in remaining_ids


def test_delete_entry_raises_when_tx_is_closed(db_session):
    tx = _open_tx(db_session, total="50.00")
    entry = add_entry(tx, "payment", "30.00")
    close_transaction(tx)

    with pytest.raises(LedgerError, match="closed"):
        delete_entry(entry)


# ---------------------------------------------------------------------------
# close_transaction
# ---------------------------------------------------------------------------


def test_close_transaction_sets_closed_at(db_session):
    tx = _open_tx(db_session)
    result = close_transaction(tx)

    db_session.refresh(tx)
    assert result is tx
    assert tx.is_closed
    assert tx.closed_at is not None


def test_close_transaction_raises_when_already_closed(db_session):
    tx = _open_tx(db_session)
    close_transaction(tx)

    with pytest.raises(LedgerError, match="already closed"):
        close_transaction(tx)


# ---------------------------------------------------------------------------
# reopen_transaction
# ---------------------------------------------------------------------------


def test_reopen_transaction_clears_closed_at(db_session):
    tx = _open_tx(db_session)
    close_transaction(tx)

    result = reopen_transaction(tx)

    db_session.refresh(tx)
    assert result is tx
    assert not tx.is_closed
    assert tx.closed_at is None


def test_reopen_transaction_raises_when_already_open(db_session):
    tx = _open_tx(db_session)

    with pytest.raises(LedgerError, match="already open"):
        reopen_transaction(tx)
