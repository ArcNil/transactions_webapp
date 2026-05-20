"""add product_type to products

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-05-19

Adds a product_type column ('sale' | 'purchase') to the products table.

Data migration:
  - Products that already have a vendor_id are assumed to be purchasable raw materials
    → set to 'purchase'.
  - All other products default to 'sale'.
"""

from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'h2i3j4k5l6m7'
branch_labels = None
depends_on = None


def upgrade():
    # Add the column as nullable first so the data migration can run.
    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(
            sa.Column("product_type", sa.String(16), nullable=True)
        )

    # Data migration: products with a vendor_id are purchase items.
    op.execute(
        "UPDATE products SET product_type = 'purchase' WHERE vendor_id IS NOT NULL"
    )
    op.execute(
        "UPDATE products SET product_type = 'sale' WHERE vendor_id IS NULL"
    )

    # Enforce NOT NULL and add a CHECK constraint so only valid values can ever be stored.
    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column("product_type", nullable=False)
        batch_op.create_check_constraint(
            "ck_products_product_type",
            "product_type IN ('sale', 'purchase')",
        )


def downgrade():
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("ck_products_product_type", type_="check")
        batch_op.drop_column("product_type")
