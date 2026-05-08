from decimal import Decimal

from app.models.product import Product
from app.models.stock import StockItem, ProductIngredient


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
