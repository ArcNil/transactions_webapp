import pytest
from decimal import Decimal
from unittest.mock import patch

from app import db
from app.models.product import Product
from app.models.vendor import Vendor
from app.services.vendor_service import VendorError, add_vendor, delete_vendor, edit_vendor


class TestAddVendor:
    def test_happy_path_returns_persisted_vendor(self, app, db_session):
        vendor = add_vendor("Fresh Springs", user_id=1, username="admin")

        assert vendor.id is not None
        assert vendor.name == "Fresh Springs"
        assert db_session.get(Vendor, vendor.id) is not None

    def test_integrity_error_raises_vendor_error(self, app, sample_vendor, db_session):
        with pytest.raises(VendorError, match='already exists'):
            add_vendor(sample_vendor.name, user_id=1, username="admin")

    def test_generic_exception_rolls_back_and_reraises(self, app, db_session):
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                add_vendor("Some Vendor", user_id=1, username="admin")
        mock_rollback.assert_called_once()


class TestEditVendor:
    def test_happy_path_updates_vendor_name(self, app, sample_vendor, db_session):
        updated = edit_vendor(sample_vendor, "Renamed Vendor", user_id=1, username="admin")
        db_session.refresh(sample_vendor)

        assert updated is sample_vendor
        assert sample_vendor.name == "Renamed Vendor"

    def test_integrity_error_raises_vendor_error(self, app, sample_vendor, db_session):
        other = Vendor(name="Other Vendor")
        db_session.add(other)
        db_session.commit()

        with pytest.raises(VendorError, match='already exists'):
            edit_vendor(sample_vendor, "Other Vendor", user_id=1, username="admin")

    def test_generic_exception_rolls_back_and_reraises(self, app, sample_vendor, db_session):
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                edit_vendor(sample_vendor, "New Name", user_id=1, username="admin")
        mock_rollback.assert_called_once()


class TestDeleteVendor:
    def test_happy_path_removes_vendor_from_db(self, app, sample_vendor, db_session):
        vendor_id = sample_vendor.id
        delete_vendor(sample_vendor, user_id=1, username="admin")

        assert db_session.get(Vendor, vendor_id) is None

    def test_raises_vendor_error_when_vendor_has_linked_products(self, app, sample_vendor, db_session):
        product = Product(
            name="Linked Product",
            unit="unit",
            price=Decimal("10.00"),
            stock=Decimal("5"),
            vendor_id=sample_vendor.id,
        )
        db_session.add(product)
        db_session.commit()

        with pytest.raises(VendorError, match="linked products"):
            delete_vendor(sample_vendor, user_id=1, username="admin")

    def test_generic_exception_rolls_back_and_reraises(self, app, sample_vendor, db_session):
        with patch.object(db.session, "commit", side_effect=Exception("DB error")), \
             patch.object(db.session, "rollback") as mock_rollback:
            with pytest.raises(Exception, match="DB error"):
                delete_vendor(sample_vendor, user_id=1, username="admin")
        mock_rollback.assert_called_once()
