from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, SubmitField
from wtforms.validators import DataRequired, NumberRange


class StockItemForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    unit = StringField("Unit (e.g. liter, kg, piece)", validators=[DataRequired()])
    submit = SubmitField("Save")


class StockAdjustForm(FlaskForm):
    quantity = DecimalField("Quantity to Add", places=4, validators=[DataRequired(), NumberRange(min=0.0001)])
    submit = SubmitField("Add Stock")
