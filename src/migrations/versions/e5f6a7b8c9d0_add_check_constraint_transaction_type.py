"""Add CHECK constraint on transaction_type

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-05-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_transactions_transaction_type',
            "transaction_type IN ('sale', 'restock', 'stock_restock')"
        )


def downgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_constraint(
            'ck_transactions_transaction_type',
            type_='check'
        )
