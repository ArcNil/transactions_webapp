from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, BooleanField, SubmitField
from wtforms.validators import DataRequired, NumberRange


class ProductForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    unit = StringField("Unit (e.g. gallon, bucket)", validators=[DataRequired()])
    price = DecimalField("Price", places=2, validators=[DataRequired(), NumberRange(min=0)])
    is_active = BooleanField("Active", default=True)
    show_in_pos = BooleanField("Show in POS", default=True)
    submit = SubmitField("Save")
