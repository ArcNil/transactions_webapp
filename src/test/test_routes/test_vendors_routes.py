from app.models.vendor import Vendor
from app.models.product import Product


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------


def test_index_unauthenticated(client):
    response = client.get("/vendors/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_index_authenticated(logged_in_client, sample_vendor):
    response = logged_in_client.get("/vendors/")
    assert response.status_code == 200
    assert b"Test Vendor Co." in response.data


def test_index_empty(logged_in_client):
    response = logged_in_client.get("/vendors/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


def test_add_unauthenticated(client):
    response = client.post("/vendors/add", data={"name": "New Vendor"})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_add_valid(logged_in_client):
    response = logged_in_client.post(
        "/vendors/add",
        data={"name": "Brand New Vendor"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Brand New Vendor" in response.data
    vendor = Vendor.query.filter_by(name="Brand New Vendor").first()
    assert vendor is not None


def test_add_empty_name(logged_in_client):
    response = logged_in_client.post(
        "/vendors/add",
        data={"name": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"This field is required" in response.data
    vendor = Vendor.query.filter_by(name="").first()
    assert vendor is None


# ---------------------------------------------------------------------------
# edit
# ---------------------------------------------------------------------------


def test_edit_unauthenticated(client, sample_vendor):
    response = client.post(
        f"/vendors/{sample_vendor.id}/edit",
        data={"name": "Updated Name"},
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_edit_valid(logged_in_client, db_session, sample_vendor):
    response = logged_in_client.post(
        f"/vendors/{sample_vendor.id}/edit",
        data={"name": "Updated Vendor Name"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Updated Vendor Name" in response.data
    db_session.refresh(sample_vendor)
    assert sample_vendor.name == "Updated Vendor Name"


def test_edit_empty_name(logged_in_client, db_session, sample_vendor):
    original_name = sample_vendor.name
    response = logged_in_client.post(
        f"/vendors/{sample_vendor.id}/edit",
        data={"name": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"This field is required" in response.data
    db_session.refresh(sample_vendor)
    assert sample_vendor.name == original_name


def test_edit_not_found(logged_in_client):
    response = logged_in_client.post("/vendors/9999/edit", data={"name": "Ghost"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_unauthenticated(client, sample_vendor):
    response = client.post(f"/vendors/{sample_vendor.id}/delete")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_delete_no_products(logged_in_client, db_session, sample_vendor):
    vendor_id = sample_vendor.id
    response = logged_in_client.post(
        f"/vendors/{vendor_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"removed" in response.data
    assert db_session.get(Vendor, vendor_id) is None


def test_delete_with_products(logged_in_client, db_session, sample_vendor):
    product = Product(
        name="Linked Product",
        unit="piece",
        price="10.00",
        stock=5,
    )
    product.vendor_id = sample_vendor.id
    db_session.add(product)
    db_session.commit()

    vendor_id = sample_vendor.id
    response = logged_in_client.post(
        f"/vendors/{vendor_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Cannot delete" in response.data
    assert db_session.get(Vendor, vendor_id) is not None


def test_delete_not_found(logged_in_client):
    response = logged_in_client.post("/vendors/9999/delete")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# duplicate name
# ---------------------------------------------------------------------------


def test_add_duplicate_name(logged_in_client, sample_vendor):
    """Submitting a name that already exists flashes an error and does not crash."""
    response = logged_in_client.post(
        "/vendors/add",
        data={"name": sample_vendor.name},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"already exists" in response.data
    # Only one vendor with that name should exist.
    assert Vendor.query.filter_by(name=sample_vendor.name).count() == 1


def test_edit_duplicate_name(logged_in_client, db_session, sample_vendor):
    """Renaming a vendor to an already-taken name flashes an error and does not crash."""
    other = Vendor(name="Other Vendor")
    db_session.add(other)
    db_session.commit()

    response = logged_in_client.post(
        f"/vendors/{other.id}/edit",
        data={"name": sample_vendor.name},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"already exists" in response.data
    db_session.refresh(other)
    assert other.name == "Other Vendor"


def test_add_whitespace_name(logged_in_client):
    """A whitespace-only name is rejected by form validation."""
    response = logged_in_client.post(
        "/vendors/add",
        data={"name": "   "},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"This field is required" in response.data
    assert Vendor.query.count() == 0
