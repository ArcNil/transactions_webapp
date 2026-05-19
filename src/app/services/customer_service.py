from sqlalchemy.exc import IntegrityError

from app import db
from app.models.customer import Customer
from app.utils.monitor import record_action


class CustomerError(ValueError):
    """Raised when a customer operation cannot be completed."""


def get_all_customers() -> list[Customer]:
    """Return all customers ordered by name."""
    return Customer.query.order_by(Customer.name).all()


def add_customer(form, user_id: int, username: str) -> Customer:
    """Create and persist a new customer from a validated CustomerForm."""
    customer = Customer(name=form.name.data)
    db.session.add(customer)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "customer.added", customer.name)
    return customer


def edit_customer(customer: Customer, form, user_id: int, username: str) -> Customer:
    """Update an existing customer's name from a validated CustomerForm."""
    customer.name = form.name.data
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "customer.edited", customer.name)
    return customer


def delete_customer(customer: Customer, user_id: int, username: str) -> None:
    """
    Delete a customer.

    Raises CustomerError if the customer has linked transactions.
    """
    if customer.transactions:
        raise CustomerError(
            f'Cannot delete "{customer.name}" — they have linked transactions.'
        )
    name = customer.name
    db.session.delete(customer)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise CustomerError(
            f'Cannot delete "{name}" — they have linked records.'
        )
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "customer.deleted", name)
