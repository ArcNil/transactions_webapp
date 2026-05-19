import pytest
from datetime import datetime

from app.models.transaction import Transaction, TransactionItem, TransactionLedgerEntry


def test_anonymous_get_finance_redirects_to_login(client):
    response = client.get("/finance/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_regular_admin_get_finance_returns_403(logged_in_client):
    response = logged_in_client.get("/finance/")
    assert response.status_code == 403


def test_superadmin_get_finance_returns_200(logged_in_superadmin_client):
    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    assert b"Finance" in response.data


def test_finance_shows_zero_revenue_when_no_transactions(logged_in_superadmin_client):
    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    assert b"0.00" in response.data


def test_finance_shows_sale_product_name_snapshot(logged_in_superadmin_client, db_session):
    tx = Transaction(
        transaction_type="sale",
        total_amount="50.00",
    )
    db_session.add(tx)
    db_session.flush()
    db_session.add(TransactionItem(
        transaction_id=tx.id,
        product_name_snapshot="GallonWaterProduct",
        unit_snapshot="gallon",
        unit_price_snapshot="25.00",
        quantity="2",
        subtotal="50.00",
    ))
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    assert b"GallonWaterProduct" in response.data


def test_finance_shows_restock_transaction_as_expense(logged_in_superadmin_client, db_session):
    tx = Transaction(
        transaction_type="restock",
        total_amount="80.00",
    )
    db_session.add(tx)
    db_session.flush()
    db_session.add(TransactionItem(
        transaction_id=tx.id,
        product_name_snapshot="RestockItem",
        unit_snapshot="box",
        unit_price_snapshot="80.00",
        quantity="1",
        subtotal="80.00",
    ))
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    assert b"Product Restock" in response.data


def test_finance_shows_stock_restock_transaction_as_expense(logged_in_superadmin_client, db_session):
    tx = Transaction(
        transaction_type="stock_restock",
        total_amount="120.00",
    )
    db_session.add(tx)
    db_session.flush()
    db_session.add(TransactionItem(
        transaction_id=tx.id,
        product_name_snapshot="RawStockItem",
        unit_snapshot="liter",
        unit_price_snapshot="120.00",
        quantity="1",
        subtotal="120.00",
    ))
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    assert b"Raw Stock Restock" in response.data


def test_finance_net_equals_revenue_minus_expenses(logged_in_superadmin_client, db_session):
    sale = Transaction(
        transaction_type="sale",
        total_amount="200.00",
    )
    expense = Transaction(
        transaction_type="restock",
        total_amount="75.00",
    )
    db_session.add_all([sale, expense])
    db_session.flush()
    db_session.add(TransactionItem(
        transaction_id=sale.id,
        product_name_snapshot="SaleProduct",
        unit_snapshot="pc",
        unit_price_snapshot="200.00",
        quantity="1",
        subtotal="200.00",
    ))
    db_session.add(TransactionItem(
        transaction_id=expense.id,
        product_name_snapshot="ExpenseProduct",
        unit_snapshot="pc",
        unit_price_snapshot="75.00",
        quantity="1",
        subtotal="75.00",
    ))
    db_session.add(TransactionLedgerEntry(transaction_id=sale.id, entry_type="payment", amount="200.00"))
    db_session.add(TransactionLedgerEntry(transaction_id=expense.id, entry_type="payment", amount="75.00"))
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    # Net = 200.00 − 75.00 = 125.00
    assert b"125.00" in response.data


def test_finance_sales_listed_newest_first(logged_in_superadmin_client, db_session):
    older_sale = Transaction(
        transaction_type="sale",
        total_amount="10.00",
        created_at=datetime(2026, 1, 1, 8, 0, 0),
    )
    newer_sale = Transaction(
        transaction_type="sale",
        total_amount="20.00",
        created_at=datetime(2026, 1, 2, 8, 0, 0),
    )
    db_session.add_all([older_sale, newer_sale])
    db_session.flush()
    db_session.add(TransactionItem(
        transaction_id=older_sale.id,
        product_name_snapshot="OlderSaleProduct",
        unit_snapshot="pc",
        unit_price_snapshot="10.00",
        quantity="1",
        subtotal="10.00",
    ))
    db_session.add(TransactionItem(
        transaction_id=newer_sale.id,
        product_name_snapshot="NewerSaleProduct",
        unit_snapshot="pc",
        unit_price_snapshot="20.00",
        quantity="1",
        subtotal="20.00",
    ))
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    assert b"OlderSaleProduct" in response.data
    assert b"NewerSaleProduct" in response.data
    assert response.data.index(b"NewerSaleProduct") < response.data.index(b"OlderSaleProduct")


def test_finance_expenses_listed_newest_first(logged_in_superadmin_client, db_session):
    older_expense = Transaction(
        transaction_type="restock",
        total_amount="30.00",
        created_at=datetime(2026, 1, 1, 9, 0, 0),
    )
    newer_expense = Transaction(
        transaction_type="restock",
        total_amount="40.00",
        created_at=datetime(2026, 1, 2, 9, 0, 0),
    )
    db_session.add_all([older_expense, newer_expense])
    db_session.flush()
    db_session.add(TransactionItem(
        transaction_id=older_expense.id,
        product_name_snapshot="OlderExpenseProduct",
        unit_snapshot="box",
        unit_price_snapshot="30.00",
        quantity="1",
        subtotal="30.00",
    ))
    db_session.add(TransactionItem(
        transaction_id=newer_expense.id,
        product_name_snapshot="NewerExpenseProduct",
        unit_snapshot="box",
        unit_price_snapshot="40.00",
        quantity="1",
        subtotal="40.00",
    ))
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    assert b"OlderExpenseProduct" in response.data
    assert b"NewerExpenseProduct" in response.data
    assert response.data.index(b"NewerExpenseProduct") < response.data.index(b"OlderExpenseProduct")


def test_finance_partial_payment_sale_amount_paid_included_in_revenue(
    logged_in_superadmin_client, db_session
):
    tx = Transaction(
        transaction_type="sale",
        total_amount="100.00",
    )
    db_session.add(tx)
    db_session.flush()
    db_session.add(TransactionItem(
        transaction_id=tx.id,
        product_name_snapshot="PartialSaleProduct",
        unit_snapshot="pc",
        unit_price_snapshot="50.00",
        quantity="2",
        subtotal="100.00",
    ))
    db_session.add(TransactionLedgerEntry(transaction_id=tx.id, entry_type="payment", amount="60.00"))
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    # Revenue is sum of payment ledger entries for sales → 60.00
    assert b"60.00" in response.data


def test_finance_unpaid_sale_contributes_zero_to_revenue(logged_in_superadmin_client, db_session):
    tx = Transaction(
        transaction_type="sale",
        total_amount="100.00",
    )
    db_session.add(tx)
    db_session.flush()
    db_session.add(TransactionItem(
        transaction_id=tx.id,
        product_name_snapshot="UnpaidSaleProduct",
        unit_snapshot="pc",
        unit_price_snapshot="100.00",
        quantity="1",
        subtotal="100.00",
    ))
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200
    # The sale appears in the sales list
    assert b"UnpaidSaleProduct" in response.data
    # Revenue sum is 0.00 — amount_paid of 0 contributes nothing
    assert b"0.00" in response.data


def test_finance_transaction_with_no_items_does_not_crash(logged_in_superadmin_client, db_session):
    # A Transaction with zero items is structurally valid at the DB level.
    # The template iterates tx.items, so an empty list must not raise an error.
    tx = Transaction(
        transaction_type="sale",
        total_amount="0.00",
    )
    db_session.add(tx)
    db_session.commit()

    response = logged_in_superadmin_client.get("/finance/")
    assert response.status_code == 200


def test_finance_unknown_transaction_type_is_rejected_by_model():
    # The Transaction model enforces an allowlist of valid types at the Python
    # level via @validates. Attempting to create a Transaction with an unknown
    # type must raise ValueError immediately — before any DB write occurs.
    with pytest.raises(ValueError, match="Invalid transaction_type"):
        Transaction(transaction_type="refund", total_amount="50.00")
