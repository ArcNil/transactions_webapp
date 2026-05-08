from app.forms.customer import CustomerForm


def test_customer_form_validates_with_name(app):
    with app.test_request_context("/"):
        form = CustomerForm(data={"name": "Maria Santos"})
        assert form.validate()


def test_customer_form_fails_when_name_is_empty(app):
    with app.test_request_context("/"):
        form = CustomerForm(data={"name": ""})
        assert not form.validate()
        assert "name" in form.errors
