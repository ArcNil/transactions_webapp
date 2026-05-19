"""Add product_restock to transaction_type CHECK constraint

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-05-19

"""
from alembic import op


revision = 'h2i3j4k5l6m7'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_constraint('ck_transactions_transaction_type', type_='check')
        batch_op.create_check_constraint(
            'ck_transactions_transaction_type',
            "transaction_type IN ('sale', 'restock', 'stock_restock', 'product_restock')"
        )


def downgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_constraint('ck_transactions_transaction_type', type_='check')
        batch_op.create_check_constraint(
            'ck_transactions_transaction_type',
            "transaction_type IN ('sale', 'restock', 'stock_restock')"
        )
