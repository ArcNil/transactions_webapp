"""add photo_data to products

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-05-20

"""
from alembic import op
import sqlalchemy as sa

revision = 'i3j4k5l6m7n8'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('photo_data', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('products', 'photo_data')
