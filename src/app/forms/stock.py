from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional


class StockItemForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    unit = StringField("Unit (e.g. liter, kg, piece)", validators=[DataRequired()])
    vendor_id = SelectField("Vendor", coerce=int, validators=[Optional()])
    submit = SubmitField("Save")


class StockAdjustForm(FlaskForm):
    quantity = DecimalField("Quantity to Add", places=4, validators=[DataRequired(), NumberRange(min=0.0001)])
    submit = SubmitField("Add Stock")
