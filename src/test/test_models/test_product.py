import pytest
from sqlalchemy.exc import IntegrityError

from app.models.product import Product


def test_product_can_be_created_with_all_fields(db_session):
    product = Product(name="Bucket", unit="pcs", price="20.00", is_active=True)
    db_session.add(product)
    db_session.commit()

    saved = db_session.get(Product, product.id)
    assert saved.name == "Bucket"
    assert saved.unit == "pcs"
    assert float(saved.price) == 20.00
    assert saved.is_active is True


def test_is_active_defaults_to_true(db_session):
    product = Product(name="Default Active", unit="gallon", price="10.00")
    db_session.add(product)
    db_session.commit()

    assert product.is_active is True


def test_created_at_is_set_automatically(db_session):
    product = Product(name="Time Test", unit="litre", price="5.00")
    db_session.add(product)
    db_session.commit()

    assert product.created_at is not None


def test_name_cannot_be_null(db_session):
    product = Product(name=None, unit="pcs", price="10.00")
    db_session.add(product)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unit_cannot_be_null(db_session):
    product = Product(name="No Unit", unit=None, price="10.00")
    db_session.add(product)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_price_cannot_be_null(db_session):
    product = Product(name="No Price", unit="pcs", price=None)
    db_session.add(product)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
