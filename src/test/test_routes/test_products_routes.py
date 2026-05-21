import io
from decimal import Decimal

from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient
from app.models.vendor import Vendor


def test_products_index_returns_200_when_authenticated(logged_in_client):
    response = logged_in_client.get("/products/")
    assert response.status_code == 200


def test_products_index_redirects_to_login_if_anonymous(client):
    response = client.get("/products/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_products_add_creates_product_and_flashes_success(logged_in_client, db_session):
    response = logged_in_client.post(
        "/products/add",
        data={"name": "New Gallon", "unit": "gallon", "price": "25.00", "is_active": "y"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added" in response.data

    product = Product.query.filter_by(name="New Gallon").first()
    assert product is not None
    assert product.unit == "gallon"


def test_products_add_with_missing_name_flashes_error(logged_in_client, db_session):
    response = logged_in_client.post(
        "/products/add",
        data={"name": "", "unit": "gallon", "price": "25.00"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"required" in response.data

    assert Product.query.count() == 0


def test_products_edit_updates_product_fields(logged_in_client, sample_product, db_session):
    product_id = sample_product.id
    response = logged_in_client.post(
        f"/products/{product_id}/edit",
        data={"name": "Premium Gallon", "unit": "gallon", "price": "75.00", "is_active": "y"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"updated" in response.data

    updated = db_session.get(Product, product_id)
    assert updated.name == "Premium Gallon"
    assert float(updated.price) == 75.00


def test_products_delete_deactivates_product(logged_in_client, sample_product, db_session):
    product_id = sample_product.id
    response = logged_in_client.post(
        f"/products/{product_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"deactivated" in response.data

    product = db_session.get(Product, product_id)
    assert product.is_active is False


def test_products_add_with_negative_price_flashes_error(logged_in_client, db_session):
    response = logged_in_client.post(
        "/products/add",
        data={"name": "Cheap Water", "unit": "gallon", "price": "-5.00"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert Product.query.count() == 0


def test_products_edit_nonexistent_product_returns_404(logged_in_client):
    response = logged_in_client.post(
        "/products/99999/edit",
        data={"name": "Ghost", "unit": "gallon", "price": "10.00", "is_active": "y"},
    )
    assert response.status_code == 404


def test_products_delete_nonexistent_product_returns_404(logged_in_client):
    response = logged_in_client.post("/products/99999/delete")
    assert response.status_code == 404


def test_products_index_renders_product_with_ingredients(logged_in_client, db_session):
    product = Product(name="Ingredient Gallon", unit="gallon", price="40.00")
    db_session.add(product)
    db_session.flush()

    stock_item = StockItem(name="Spring Water", unit="liter", quantity=Decimal("10"))
    db_session.add(stock_item)
    db_session.flush()

    ingredient = ProductIngredient(
        product_id=product.id, stock_item_id=stock_item.id, quantity=Decimal("2")
    )
    db_session.add(ingredient)
    db_session.commit()

    response = logged_in_client.get("/products/")
    assert response.status_code == 200
    assert b"Ingredient Gallon" in response.data


def test_products_edit_with_invalid_form_flashes_error(logged_in_client, sample_product, db_session):
    product_id = sample_product.id
    response = logged_in_client.post(
        f"/products/{product_id}/edit",
        data={"name": "", "unit": "gallon", "price": "50.00", "is_active": "y"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"required" in response.data

    db_session.refresh(sample_product)
    assert sample_product.name == "Water Gallon"


def test_products_toggle_pos_shows_product_in_pos(logged_in_client, sample_product, db_session):
    product_id = sample_product.id
    sample_product.show_in_pos = False
    db_session.commit()

    response = logged_in_client.post(
        f"/products/{product_id}/toggle_pos",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"shown in" in response.data

    db_session.refresh(sample_product)
    assert sample_product.show_in_pos is True


def test_products_toggle_pos_hides_product_from_pos(logged_in_client, sample_product, db_session):
    product_id = sample_product.id
    # sample_product.show_in_pos is True by default

    response = logged_in_client.post(
        f"/products/{product_id}/toggle_pos",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"hidden from" in response.data

    db_session.refresh(sample_product)
    assert sample_product.show_in_pos is False


# ---------------------------------------------------------------------------
# BACK-002: hide deactivated products / show-inactive toggle
# ---------------------------------------------------------------------------


def test_products_index_hides_inactive_product_by_default(logged_in_client, db_session):
    product = Product(name="Discontinued Gallon", unit="gallon", price="10.00", is_active=False)
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/products/")
    assert response.status_code == 200
    assert b"Discontinued Gallon" not in response.data


def test_products_index_shows_active_product_by_default(logged_in_client, sample_product):
    response = logged_in_client.get("/products/")
    assert response.status_code == 200
    assert b"Water Gallon" in response.data


def test_products_index_show_inactive_1_reveals_inactive_product(logged_in_client, db_session):
    product = Product(name="Retired Bottle", unit="bottle", price="5.00", is_active=False)
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/products/?show_inactive=1")
    assert response.status_code == 200
    assert b"Retired Bottle" in response.data


def test_products_index_show_inactive_0_hides_inactive_product(logged_in_client, db_session):
    product = Product(name="Old Container", unit="container", price="8.00", is_active=False)
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/products/?show_inactive=0")
    assert response.status_code == 200
    assert b"Old Container" not in response.data


def test_products_index_show_inactive_arbitrary_value_hides_inactive_product(logged_in_client, db_session):
    product = Product(name="Legacy Jug", unit="jug", price="12.00", is_active=False)
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/products/?show_inactive=yes")
    assert response.status_code == 200
    assert b"Legacy Jug" not in response.data


def test_products_index_shows_toggle_button_when_inactive_products_exist(logged_in_client, db_session):
    product = Product(name="Deactivated Item", unit="gallon", price="20.00", is_active=False)
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.get("/products/")
    assert response.status_code == 200
    assert b"show_inactive=1" in response.data


def test_products_index_hides_toggle_button_when_no_inactive_products_exist(
    logged_in_client, sample_product
):
    # sample_product is active; no inactive products exist in this test's db.
    response = logged_in_client.get("/products/")
    assert response.status_code == 200
    assert b"show_inactive=1" not in response.data


def test_products_ingredient_add_with_invalid_quantity_flashes_danger(
    logged_in_client, sample_product, db_session
):
    product_id = sample_product.id
    response = logged_in_client.post(
        f"/products/{product_id}/ingredients/add",
        data={"stock_item_id": "0", "quantity": "abc"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Invalid" in response.data


def test_products_ingredient_delete_removes_ingredient(logged_in_client, sample_product, db_session):
    stock_item = StockItem(name="Test Water", unit="liter", quantity=Decimal("5"))
    db_session.add(stock_item)
    db_session.flush()

    ingredient = ProductIngredient(
        product_id=sample_product.id, stock_item_id=stock_item.id, quantity=Decimal("1")
    )
    db_session.add(ingredient)
    db_session.commit()

    ingredient_id = ingredient.id
    product_id = sample_product.id

    response = logged_in_client.post(
        f"/products/{product_id}/ingredients/{ingredient_id}/delete",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Removed" in response.data

    assert db_session.get(ProductIngredient, ingredient_id) is None


def test_products_ingredient_delete_with_wrong_product_id_returns_404(
    logged_in_client, sample_product, db_session
):
    other_product = Product(name="Other Product", unit="unit", price="10.00")
    db_session.add(other_product)
    db_session.flush()

    stock_item = StockItem(name="Salt Water", unit="liter", quantity=Decimal("5"))
    db_session.add(stock_item)
    db_session.flush()

    ingredient = ProductIngredient(
        product_id=other_product.id, stock_item_id=stock_item.id, quantity=Decimal("1")
    )
    db_session.add(ingredient)
    db_session.commit()

    response = logged_in_client.post(
        f"/products/{sample_product.id}/ingredients/{ingredient.id}/delete",
    )
    assert response.status_code == 404


def test_products_ingredient_add_happy_path(logged_in_client, sample_product, sample_stock_item, db_session):
    product_id = sample_product.id
    response = logged_in_client.post(
        f"/products/{product_id}/ingredients/add",
        data={"stock_item_id": str(sample_stock_item.id), "quantity": "2.5"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Added" in response.data

    ingredient = ProductIngredient.query.filter_by(
        product_id=product_id, stock_item_id=sample_stock_item.id
    ).first()
    assert ingredient is not None
    assert ingredient.stock_item_id == sample_stock_item.id
    assert ingredient.quantity == Decimal("2.5")


def test_products_ingredient_add_requires_login(client):
    response = client.post(
        "/products/1/ingredients/add",
        data={"stock_item_id": "1", "quantity": "1.0"},
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_products_ingredient_delete_requires_login(client):
    response = client.post("/products/1/ingredients/1/delete")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_products_toggle_pos_nonexistent_product_returns_404(logged_in_client):
    response = logged_in_client.post("/products/99999/toggle_pos")
    assert response.status_code == 404


def test_products_ingredient_add_nonexistent_product_returns_404(logged_in_client):
    response = logged_in_client.post(
        "/products/99999/ingredients/add",
        data={"stock_item_id": "1", "quantity": "1.0"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# vendor_id extraction — POST /products/add
# ---------------------------------------------------------------------------


def test_add_product_with_valid_vendor_id_stores_vendor(
    logged_in_client, sample_vendor, db_session
):
    response = logged_in_client.post(
        "/products/add",
        data={
            "name": "Vendor Gallon",
            "unit": "gallon",
            "price": "30.00",
            "is_active": "y",
            "vendor_id": str(sample_vendor.id),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added" in response.data

    product = Product.query.filter_by(name="Vendor Gallon").first()
    assert product is not None
    assert product.vendor_id == sample_vendor.id


def test_add_product_with_vendor_id_zero_stores_none(logged_in_client, db_session):
    response = logged_in_client.post(
        "/products/add",
        data={
            "name": "Zero Vendor Gallon",
            "unit": "gallon",
            "price": "30.00",
            "is_active": "y",
            "vendor_id": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added" in response.data

    product = Product.query.filter_by(name="Zero Vendor Gallon").first()
    assert product is not None
    assert product.vendor_id is None


def test_add_product_with_non_numeric_vendor_id_stores_none(logged_in_client, db_session):
    response = logged_in_client.post(
        "/products/add",
        data={
            "name": "NoVendor Gallon",
            "unit": "gallon",
            "price": "30.00",
            "is_active": "y",
            "vendor_id": "abc",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added" in response.data

    product = Product.query.filter_by(name="NoVendor Gallon").first()
    assert product is not None
    assert product.vendor_id is None


def test_add_product_with_nonexistent_vendor_id_stores_vendor_id_anyway(
    logged_in_client, db_session
):
    # SQLite does NOT enforce FK constraints by default, so committing a
    # Product with vendor_id=99999 (no matching Vendor row) succeeds without
    # raising an IntegrityError.  The route passes the raw integer straight to
    # add_product() without validating FK existence first.
    response = logged_in_client.post(
        "/products/add",
        data={
            "name": "Ghost Vendor Gallon",
            "unit": "gallon",
            "price": "30.00",
            "is_active": "y",
            "vendor_id": "99999",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added" in response.data

    product = Product.query.filter_by(name="Ghost Vendor Gallon").first()
    assert product is not None
    assert product.vendor_id == 99999


# ---------------------------------------------------------------------------
# vendor_id extraction — POST /products/<id>/edit
# ---------------------------------------------------------------------------


def test_edit_product_with_valid_vendor_id_updates_vendor(
    logged_in_client, sample_product, sample_vendor, db_session
):
    product_id = sample_product.id
    response = logged_in_client.post(
        f"/products/{product_id}/edit",
        data={
            "name": sample_product.name,
            "unit": sample_product.unit,
            "price": str(sample_product.price),
            "is_active": "y",
            "vendor_id": str(sample_vendor.id),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"updated" in response.data

    db_session.refresh(sample_product)
    assert sample_product.vendor_id == sample_vendor.id


def test_edit_product_clears_vendor_when_vendor_id_is_zero(
    logged_in_client, sample_product, sample_vendor, db_session
):
    sample_product.vendor_id = sample_vendor.id
    db_session.commit()

    product_id = sample_product.id
    response = logged_in_client.post(
        f"/products/{product_id}/edit",
        data={
            "name": sample_product.name,
            "unit": sample_product.unit,
            "price": str(sample_product.price),
            "is_active": "y",
            "vendor_id": "0",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"updated" in response.data

    db_session.refresh(sample_product)
    assert sample_product.vendor_id is None


# ---------------------------------------------------------------------------
# toggle_pos — purchase-type guard (route level)
# ---------------------------------------------------------------------------


def test_products_toggle_pos_purchase_type_flashes_danger(logged_in_client, db_session):
    product = Product(
        name="Raw Material",
        unit="kg",
        price="5.00",
        stock=Decimal("10"),
        product_type="purchase",
        show_in_pos=False,
    )
    db_session.add(product)
    db_session.commit()

    response = logged_in_client.post(
        f"/products/{product.id}/toggle_pos",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Purchase products cannot" in response.data

    db_session.refresh(product)
    assert product.show_in_pos is False


# ---------------------------------------------------------------------------
# photo upload — POST /products/add and /products/<id>/edit
# ---------------------------------------------------------------------------


def test_add_product_with_valid_photo_stores_data_uri(logged_in_client, db_session):
    jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 50
    response = logged_in_client.post(
        "/products/add",
        data={
            "name": "Photo Product",
            "unit": "gallon",
            "price": "10.00",
            "is_active": "y",
            "photo": (io.BytesIO(jpeg_bytes), "test.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"added" in response.data

    product = Product.query.filter_by(name="Photo Product").first()
    assert product is not None
    assert product.photo_data is not None
    assert product.photo_data.startswith("data:image/jpeg;base64,")


def test_add_product_with_oversized_photo_flashes_error(logged_in_client, db_session):
    big_bytes = b"\xff\xd8\xff" + b"\x00" * (2 * 1024 * 1024)  # > 2 MB
    response = logged_in_client.post(
        "/products/add",
        data={
            "name": "BigPhoto Product",
            "unit": "gallon",
            "price": "10.00",
            "is_active": "y",
            "photo": (io.BytesIO(big_bytes), "big.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"2 MB" in response.data
    assert Product.query.filter_by(name="BigPhoto Product").first() is None


def test_add_product_with_wrong_magic_bytes_flashes_error(logged_in_client, db_session):
    bad_bytes = b"not an image at all"
    response = logged_in_client.post(
        "/products/add",
        data={
            "name": "BadMagic Product",
            "unit": "gallon",
            "price": "10.00",
            "is_active": "y",
            "photo": (io.BytesIO(bad_bytes), "fake.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Unsupported" in response.data
    assert Product.query.filter_by(name="BadMagic Product").first() is None


def test_edit_product_remove_photo_clears_photo_data(
    logged_in_client, sample_product, db_session
):
    sample_product.photo_data = "data:image/jpeg;base64,/9j/ABC"
    db_session.commit()

    product_id = sample_product.id
    response = logged_in_client.post(
        f"/products/{product_id}/edit",
        data={
            "name": sample_product.name,
            "unit": sample_product.unit,
            "price": str(sample_product.price),
            "is_active": "y",
            "remove_photo": "on",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"updated" in response.data

    db_session.refresh(sample_product)
    assert sample_product.photo_data is None
