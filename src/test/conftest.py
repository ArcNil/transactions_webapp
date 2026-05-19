import os
import sys

# Ensure src/ is on the path so that "from app import ..." works from any
# working directory that pytest is invoked from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set required environment variables BEFORE importing the app module so that
# create_app() can read them on the first call.
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WEB_APP_TITLE"] = "H2O"

import pytest
from decimal import Decimal
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

from app import create_app
from app import db as _db
from app.models.user import User
from app.models.product import Product
from app.models.customer import Customer
from app.models.transaction import Transaction, TransactionItem, TransactionLedgerEntry
from app.models.vendor import Vendor
from app.models.stock import StockItem


@pytest.fixture(scope="function")
def app():
    """
    Create a fresh Flask application configured for testing.

    Each test gets its own SQLite in-memory database.  StaticPool ensures
    every connection within the test shares the same in-memory store, so
    data written by fixtures is visible to the route handlers.
    """
    application = create_app()
    application.config.update(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        }
    )

    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Flask test client bound to the test application."""
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    """
    SQLAlchemy session for the current test.

    Depends on *app* so the session is always used within an active
    application context.
    """
    yield _db.session


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def sample_user(db_session):
    user = User(
        username="testuser",
        password_hash=generate_password_hash("password123"),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture(scope="function")
def sample_product(db_session):
    product = Product(
        name="Water Gallon",
        unit="gallon",
        price="50.00",
        stock=Decimal("100"),
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture(scope="function")
def sample_customer(db_session):
    customer = Customer(name="Juan dela Cruz")
    db_session.add(customer)
    db_session.commit()
    return customer


@pytest.fixture(scope="function")
def sample_transaction(db_session, sample_product):
    """A persisted Transaction with one TransactionItem (2 units of sample_product).

    NOTE: This fixture inserts rows directly without going through create_transaction.
    As a result, sample_product.stock is NOT decremented. Tests that assert on
    stock levels after calling create_transaction or update_transaction should
    set up their own product and transaction rather than relying on this fixture.
    """
    tx = Transaction(
        customer_id=None,
        transaction_type="sale",
        total_amount=str(Decimal(sample_product.price) * 2),
    )
    db_session.add(tx)
    db_session.flush()
    item = TransactionItem(
        transaction_id=tx.id,
        product_id=sample_product.id,
        product_name_snapshot=sample_product.name,
        unit_snapshot=sample_product.unit,
        unit_price_snapshot=sample_product.price,
        quantity="2",
        subtotal=str(Decimal(sample_product.price) * 2),
    )
    db_session.add(item)
    db_session.commit()
    return tx


@pytest.fixture(scope="function")
def logged_in_client(client, sample_user):
    """
    Test client that is already authenticated as *sample_user*.

    Logs in via POST /login so the session cookie is set correctly.
    """
    client.post(
        "/login",
        data={"username": "testuser", "password": "password123"},
        follow_redirects=True,
    )
    yield client


@pytest.fixture(scope="function")
def superadmin_user(db_session):
    user = User(
        username="superadmin",
        password_hash=generate_password_hash("superpass123"),
        role=User.ROLE_SUPERADMIN,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture(scope="function")
def logged_in_superadmin_client(client, superadmin_user):
    """
    Test client that is already authenticated as *superadmin_user*.

    Logs in via POST /login so the session cookie is set correctly.
    """
    client.post(
        "/login",
        data={"username": "superadmin", "password": "superpass123"},
        follow_redirects=True,
    )
    yield client


@pytest.fixture(scope="function")
def sample_vendor(db_session):
    vendor = Vendor(name="Test Vendor Co.")
    db_session.add(vendor)
    db_session.commit()
    return vendor


@pytest.fixture(scope="function")
def sample_stock_item(db_session):
    item = StockItem(name="Purified Water", unit="liter", quantity=Decimal("20"))
    db_session.add(item)
    db_session.commit()
    return item
