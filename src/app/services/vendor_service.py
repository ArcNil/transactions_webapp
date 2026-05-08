from sqlalchemy.exc import IntegrityError

from app import db
from app.models.vendor import Vendor
from app.utils.monitor import record_action


class VendorError(ValueError):
    """Raised when a vendor operation cannot be completed."""


def add_vendor(name: str, user_id: int, username: str) -> Vendor:
    """
    Create and persist a new vendor.

    Raises VendorError if a vendor with the same name already exists.
    """
    vendor = Vendor(name=name)
    db.session.add(vendor)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise VendorError(f'Vendor "{name}" already exists.')
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "vendor.added", name)
    return vendor


def edit_vendor(vendor: Vendor, name: str, user_id: int, username: str) -> Vendor:
    """
    Rename an existing vendor.

    Raises VendorError if the new name is already taken by another vendor.
    """
    vendor.name = name
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise VendorError(f'Vendor "{name}" already exists.')
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "vendor.edited", name)
    return vendor


def delete_vendor(vendor: Vendor, user_id: int, username: str) -> None:
    """
    Delete a vendor.

    Raises VendorError if the vendor has linked products.
    """
    if vendor.products:
        raise VendorError(
            f'Cannot delete "{vendor.name}" — they have linked products. '
            "Unlink the products first."
        )
    vendor_name = vendor.name
    db.session.delete(vendor)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    record_action(user_id, username, "vendor.deleted", vendor_name)
