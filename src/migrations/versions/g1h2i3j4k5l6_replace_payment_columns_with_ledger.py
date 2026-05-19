"""Replace flat payment columns with payment ledger table.

Drop amount_paid, amount_tendered, change_given, payment_status from transactions.
Add closed_at to transactions.
Create transaction_ledger_entries table.

Revision ID: g1h2i3j4k5l6
Revises: a7b8c9d0e1f2
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "g1h2i3j4k5l6"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create transaction_ledger_entries
    op.create_table(
        "transaction_ledger_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transaction_ledger_entries_transaction_id"),
        "transaction_ledger_entries",
        ["transaction_id"],
        unique=False,
    )

    # 2. Add closed_at to transactions
    op.add_column("transactions", sa.Column("closed_at", sa.DateTime(), nullable=True))

    # 3. Drop old flat payment columns
    op.drop_column("transactions", "payment_status")
    op.drop_column("transactions", "change_given")
    op.drop_column("transactions", "amount_tendered")
    op.drop_column("transactions", "amount_paid")


def downgrade():
    # Re-add old flat payment columns (with sensible defaults for existing rows)
    op.add_column(
        "transactions",
        sa.Column("amount_paid", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
    )
    op.add_column(
        "transactions",
        sa.Column("amount_tendered", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("change_given", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("payment_status", sa.String(length=16), nullable=False, server_default="unpaid"),
    )

    op.drop_column("transactions", "closed_at")

    op.drop_index(
        op.f("ix_transaction_ledger_entries_transaction_id"),
        table_name="transaction_ledger_entries",
    )
    op.drop_table("transaction_ledger_entries")
