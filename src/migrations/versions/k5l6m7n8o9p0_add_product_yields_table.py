"""add product_yields table

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-05-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'k5l6m7n8o9p0'
down_revision = 'j4k5l6m7n8o9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'product_yields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('stock_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 4), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name='product_yields_product_id_fkey'),
        sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id'], name='product_yields_stock_item_id_fkey'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'stock_item_id', name='uq_product_yields_product_stock'),
    )


def downgrade():
    op.drop_table('product_yields')
