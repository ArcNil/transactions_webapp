from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app import db
from app.models.transaction import Transaction, TransactionLedgerEntry


class LedgerError(ValueError):
    """Raised when a ledger operation is invalid."""


VALID_ENTRY_TYPES = ("payment", "change", "refund", "discount", "adjustment")


def _auto_close_if_settled(tx: Transaction) -> None:
    """If the transaction is settled and open, close it automatically."""
    if not tx.is_closed and tx.balance == Decimal("0"):
        tx.closed_at = datetime.now(timezone.utc)


def _auto_reopen_if_unsettled(tx: Transaction) -> None:
    """If the transaction was auto-closed but is no longer settled, reopen it."""
    if tx.is_closed and tx.balance != Decimal("0"):
        tx.closed_at = None


def _parse_amount(raw: str, allow_negative: bool = False) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError):
        raise LedgerError("Invalid amount.")
    if not allow_negative and value < 0:
        raise LedgerError("Amount must be zero or greater.")
    return value


def add_entry(
    tx: Transaction,
    entry_type: str,
    amount_raw: str,
    note: str | None = None,
) -> TransactionLedgerEntry:
    """
    Add a payment ledger entry to a transaction.

    Auto-closes the transaction if the resulting balance is exactly zero.
    Raises LedgerError if the transaction is closed or the input is invalid.
    """
    if tx.is_closed:
        raise LedgerError("Cannot add an entry to a closed transaction. Reopen it first.")

    if entry_type not in VALID_ENTRY_TYPES:
        raise LedgerError(f"Invalid entry type '{entry_type}'.")

    is_adjustment = entry_type == "adjustment"
    amount = _parse_amount(amount_raw, allow_negative=is_adjustment)

    entry = TransactionLedgerEntry(
        transaction_id=tx.id,
        entry_type=entry_type,
        amount=amount,
        note=note.strip()[:255] if note else None,
    )
    db.session.add(entry)
    db.session.flush()  # assigns entry.id and makes it visible on tx.ledger_entries

    # Re-evaluate auto-close after the new entry is reflected.
    db.session.refresh(tx)
    _auto_close_if_settled(tx)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return entry


def update_entry(
    entry: TransactionLedgerEntry,
    entry_type: str,
    amount_raw: str,
    note: str | None = None,
) -> TransactionLedgerEntry:
    """
    Update an existing ledger entry.

    Re-evaluates auto-close/reopen after the change.
    Raises LedgerError if the parent transaction is closed or the input is invalid.
    """
    tx = entry.transaction
    if tx.is_closed:
        raise LedgerError("Cannot edit an entry on a closed transaction. Reopen it first.")

    if entry_type not in VALID_ENTRY_TYPES:
        raise LedgerError(f"Invalid entry type '{entry_type}'.")

    is_adjustment = entry_type == "adjustment"
    amount = _parse_amount(amount_raw, allow_negative=is_adjustment)

    entry.entry_type = entry_type
    entry.amount = amount
    entry.note = note.strip()[:255] if note else None

    db.session.flush()
    db.session.refresh(tx)
    _auto_close_if_settled(tx)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return entry


def delete_entry(entry: TransactionLedgerEntry) -> None:
    """
    Delete a ledger entry.

    Re-evaluates auto-reopen after deletion (a previously settled tx may
    become unsettled once an entry is removed).
    Raises LedgerError if the parent transaction is closed.
    """
    tx = entry.transaction
    if tx.is_closed:
        raise LedgerError("Cannot delete an entry from a closed transaction. Reopen it first.")

    db.session.delete(entry)
    db.session.flush()
    db.session.refresh(tx)
    # Deletion of a change/refund/discount entry reduces total_returned, which
    # can move the balance to exactly zero — auto-close in that case.
    # Deletion of a payment entry unsettles the transaction — auto-reopen.
    _auto_close_if_settled(tx)
    _auto_reopen_if_unsettled(tx)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def close_transaction(tx: Transaction) -> Transaction:
    """Manually close a transaction regardless of its current balance."""
    if tx.is_closed:
        raise LedgerError("Transaction is already closed.")
    tx.closed_at = datetime.now(timezone.utc)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return tx


def reopen_transaction(tx: Transaction) -> Transaction:
    """Reopen a closed transaction so entries can be added or edited."""
    if not tx.is_closed:
        raise LedgerError("Transaction is already open.")
    tx.closed_at = None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return tx
