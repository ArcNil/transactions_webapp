from werkzeug.datastructures import MultiDict
from app.forms.product import ProductForm


def test_product_form_validates_with_valid_data(app):
    with app.test_request_context("/"):
        form = ProductForm(
            formdata=MultiDict({"name": "Water Gallon", "unit": "gallon", "price": "50.00", "is_active": "y"})
        )
        assert form.validate()


def test_product_form_fails_when_name_missing(app):
    with app.test_request_context("/"):
        form = ProductForm(formdata=MultiDict({"name": "", "unit": "gallon", "price": "50.00"}))
        assert not form.validate()
        assert "name" in form.errors


def test_product_form_fails_when_price_is_negative(app):
    with app.test_request_context("/"):
        form = ProductForm(formdata=MultiDict({"name": "Water", "unit": "gallon", "price": "-1.00"}))
        assert not form.validate()
        assert "price" in form.errors


def test_product_form_fails_when_unit_is_empty(app):
    with app.test_request_context("/"):
        form = ProductForm(formdata=MultiDict({"name": "Water", "unit": "", "price": "50.00"}))
        assert not form.validate()
        assert "unit" in form.errors


def test_product_form_fails_with_zero_price(app):
    # DataRequired treats Decimal('0.00') as falsy, so price=0 is rejected by the form.
    # The service layer's separate guard for custom items (price > 0) is therefore redundant
    # at the form level but still reached via the JSON cart path.
    with app.test_request_context("/"):
        form = ProductForm(formdata=MultiDict({"name": "Water", "unit": "gallon", "price": "0.00"}))
        assert not form.validate()
        assert "price" in form.errors
