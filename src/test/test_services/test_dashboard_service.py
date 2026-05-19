from datetime import datetime, timedelta, timezone

import pytest

from app.models.transaction import Transaction, TransactionLedgerEntry
from app.services.dashboard_service import get_chart_data, get_recent_transactions, get_stats


class TestGetStats:
    def test_returns_dict_with_required_keys(self, app, db_session):
        result = get_stats()

        assert "total_revenue" in result
        assert "today_revenue" in result
        assert "today_tx_count" in result

    def test_returns_zeroes_when_no_transactions(self, app, db_session):
        result = get_stats()

        assert result["total_revenue"] == 0.0
        assert result["today_revenue"] == 0.0
        assert result["today_tx_count"] == 0

    def test_counts_todays_transactions(self, app, sample_transaction, db_session):
        result = get_stats()

        assert result["today_tx_count"] == 1

    def test_sums_total_revenue_across_all_transactions(self, app, sample_transaction, db_session):
        entry = TransactionLedgerEntry(
            transaction_id=sample_transaction.id,
            entry_type="payment",
            amount=sample_transaction.total_amount,
        )
        db_session.add(entry)
        db_session.commit()

        result = get_stats()

        assert result["total_revenue"] == float(sample_transaction.total_amount)

    def test_excludes_yesterday_from_today_revenue(self, app, db_session):
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        tx = Transaction(
            transaction_type="sale",
            total_amount="200.00",
            created_at=yesterday,
        )
        db_session.add(tx)
        db_session.commit()

        result = get_stats()

        assert result["today_revenue"] == 0.0
        assert result["today_tx_count"] == 0

    def test_today_revenue_sums_only_todays_paid_amounts(self, app, db_session):
        tx1 = Transaction(transaction_type="sale", total_amount="75.00")
        tx2 = Transaction(transaction_type="sale", total_amount="25.00")
        db_session.add_all([tx1, tx2])
        db_session.commit()

        db_session.add_all([
            TransactionLedgerEntry(transaction_id=tx1.id, entry_type="payment", amount="75.00"),
            TransactionLedgerEntry(transaction_id=tx2.id, entry_type="payment", amount="25.00"),
        ])
        db_session.commit()

        result = get_stats()

        assert result["today_revenue"] == 100.0
        assert result["today_tx_count"] == 2


class TestGetRecentTransactions:
    def test_returns_transactions_newest_first(self, app, db_session):
        earlier = Transaction(
            transaction_type="sale",
            total_amount="50.00",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        later = Transaction(
            transaction_type="sale",
            total_amount="100.00",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add_all([earlier, later])
        db_session.commit()

        results = get_recent_transactions()

        assert results[0].id == later.id
        assert results[1].id == earlier.id

    def test_respects_limit_parameter(self, app, db_session):
        for _ in range(5):
            db_session.add(
                Transaction(transaction_type="sale", total_amount="10.00")
            )
        db_session.commit()

        results = get_recent_transactions(limit=3)

        assert len(results) == 3


class TestGetChartData:
    def test_returns_dict_with_required_keys(self, app, db_session):
        result = get_chart_data()

        assert "labels" in result
        assert "revenue" in result
        assert "expenses" in result
        assert "net" in result

    def test_returns_exactly_seven_entries_by_default(self, app, db_session):
        result = get_chart_data()

        assert len(result["labels"]) == 7
        assert len(result["revenue"]) == 7
        assert len(result["expenses"]) == 7
        assert len(result["net"]) == 7

    def test_respects_days_parameter(self, app, db_session):
        result = get_chart_data(days=14)

        assert len(result["labels"]) == 14
        assert len(result["revenue"]) == 14

    def test_data_values_are_floats(self, app, db_session):
        result = get_chart_data()

        for value in result["revenue"]:
            assert isinstance(value, float)
        for value in result["expenses"]:
            assert isinstance(value, float)
        for value in result["net"]:
            assert isinstance(value, float)

    def test_chart_data_places_revenue_in_correct_day_bucket(self, app, db_session):
        tx = Transaction(transaction_type="sale", total_amount="150.00")
        db_session.add(tx)
        db_session.commit()

        db_session.add(TransactionLedgerEntry(transaction_id=tx.id, entry_type="payment", amount="150.00"))
        db_session.commit()

        result = get_chart_data()

        assert result["revenue"][-1] == 150.0
