"""drop vendor_id from stock_items

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-05-21

"""
from alembic import op
import sqlalchemy as sa

revision = 'j4k5l6m7n8o9'
down_revision = 'i3j4k5l6m7n8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('stock_items') as batch_op:
        batch_op.drop_constraint('fk_stock_items_vendor_id', type_='foreignkey')
        batch_op.drop_column('vendor_id')


def downgrade():
    with op.batch_alter_table('stock_items') as batch_op:
        batch_op.add_column(sa.Column('vendor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_stock_items_vendor_id', 'vendors', ['vendor_id'], ['id']
        )
