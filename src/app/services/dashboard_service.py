from datetime import datetime, timezone, timedelta

from sqlalchemy import func, and_

from app import db
from app.models.transaction import Transaction, TransactionLedgerEntry


def _net_collected(tx_type_filter, date_filter=None):
    """
    Compute net cash collected for the given transaction type filter.

    net = payments − (change + refunds + discounts) + adjustments

    Adjustments are signed: positive = credit (reduces what is owed),
    negative = debit (increases what is owed).

    Returns a float.
    """
    CREDIT_TYPES = ("payment",)
    DEBIT_TYPES = ("change", "refund", "discount")

    base = (
        db.session.query(func.coalesce(func.sum(TransactionLedgerEntry.amount), 0))
        .join(Transaction, TransactionLedgerEntry.transaction_id == Transaction.id)
    )

    credits = base.filter(tx_type_filter, TransactionLedgerEntry.entry_type.in_(CREDIT_TYPES))
    debits = base.filter(tx_type_filter, TransactionLedgerEntry.entry_type.in_(DEBIT_TYPES))
    adjustments = base.filter(tx_type_filter, TransactionLedgerEntry.entry_type == "adjustment")

    if date_filter is not None:
        credits = credits.filter(date_filter)
        debits = debits.filter(date_filter)
        adjustments = adjustments.filter(date_filter)

    return float(credits.scalar()) - float(debits.scalar()) + float(adjustments.scalar())


def get_stats() -> dict:
    """Return aggregate revenue figures for the dashboard summary panel."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_revenue = _net_collected(Transaction.transaction_type == "sale")

    today_revenue = _net_collected(
        Transaction.transaction_type == "sale",
        date_filter=Transaction.created_at >= today_start,
    )

    today_tx_count = Transaction.query.filter(
        Transaction.transaction_type == "sale",
        Transaction.created_at >= today_start,
    ).count()

    return {
        "total_revenue": total_revenue,
        "today_revenue": today_revenue,
        "today_tx_count": today_tx_count,
    }


_EXPENSE_TYPES = ("restock", "stock_restock", "product_restock")


def get_financial_summary() -> dict:
    """Return all-time revenue, expenses, and net figures."""
    revenue = _net_collected(Transaction.transaction_type == "sale")
    expenses = _net_collected(Transaction.transaction_type.in_(_EXPENSE_TYPES))

    return {
        "revenue": revenue,
        "expenses": expenses,
        "net": revenue - expenses,
    }


def get_sales_transactions() -> list:
    """Return all sale transactions ordered newest-first."""
    return (
        Transaction.query
        .filter_by(transaction_type="sale")
        .order_by(Transaction.created_at.desc())
        .all()
    )


def get_expense_transactions() -> list:
    """Return all expense transactions (restock, stock_restock, product_restock) ordered newest-first."""
    return (
        Transaction.query
        .filter(Transaction.transaction_type.in_(_EXPENSE_TYPES))
        .order_by(Transaction.created_at.desc())
        .all()
    )


def get_recent_transactions(limit: int = 10) -> list:
    """Return the most recent transactions ordered newest-first."""
    return Transaction.query.order_by(Transaction.created_at.desc()).limit(limit).all()


def get_chart_data(days: int = 7) -> dict:
    """Return daily revenue, expense, and net totals for the last *days* days."""
    today = datetime.now(timezone.utc).date()
    labels = []
    revenue_data = []
    expense_data = []
    net_data = []

    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        day_filter = and_(Transaction.created_at >= day_start, Transaction.created_at < day_end)

        revenue = _net_collected(
            Transaction.transaction_type == "sale",
            date_filter=day_filter,
        )
        expenses = _net_collected(
            Transaction.transaction_type.in_(_EXPENSE_TYPES),
            date_filter=day_filter,
        )

        labels.append(day.strftime("%b %d"))
        revenue_data.append(revenue)
        expense_data.append(expenses)
        net_data.append(revenue - expenses)

    return {
        "labels": labels,
        "revenue": revenue_data,
        "expenses": expense_data,
        "net": net_data,
    }
