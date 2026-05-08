"""Add stock_items table, product_ingredients table, stock_item_id to transaction_items

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'stock_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('unit', sa.String(length=64), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=4), nullable=False, server_default='0'),
        sa.Column('vendor_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], name='fk_stock_items_vendor_id'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'product_ingredients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('stock_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name='fk_ingredients_product_id'),
        sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id'], name='fk_ingredients_stock_item_id'),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('transaction_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stock_item_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_txitems_stock_item_id', 'stock_items', ['stock_item_id'], ['id'])


def downgrade():
    with op.batch_alter_table('transaction_items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_txitems_stock_item_id', type_='foreignkey')
        batch_op.drop_column('stock_item_id')

    op.drop_table('product_ingredients')
    op.drop_table('stock_items')
