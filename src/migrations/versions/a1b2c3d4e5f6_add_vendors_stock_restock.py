"""Add vendors table, stock to products, transaction_type + vendor_id to transactions

Revision ID: a1b2c3d4e5f6
Revises: 333a7a3fc9d9
Create Date: 2026-04-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '333a7a3fc9d9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'vendors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stock', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('vendor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_products_vendor_id', 'vendors', ['vendor_id'], ['id'])

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('transaction_type', sa.String(length=16), nullable=False, server_default='sale'))
        batch_op.add_column(sa.Column('vendor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_transactions_vendor_id', 'vendors', ['vendor_id'], ['id'])


def downgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_transactions_vendor_id', type_='foreignkey')
        batch_op.drop_column('vendor_id')
        batch_op.drop_column('transaction_type')

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('fk_products_vendor_id', type_='foreignkey')
        batch_op.drop_column('vendor_id')
        batch_op.drop_column('stock')

    op.drop_table('vendors')
