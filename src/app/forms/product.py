from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, DecimalField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional


class ProductForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    product_type = SelectField(
        "Product type",
        choices=[("sale", "Sale — sold through POS"), ("purchase", "Purchase — restockable item")],
        default="sale",
    )
    unit = StringField("Unit (e.g. gallon, bucket)", validators=[DataRequired()])
    price = DecimalField("Price", places=2, validators=[DataRequired(), NumberRange(min=0)])
    is_active = BooleanField("Active", default=True)
    show_in_pos = BooleanField("Show in POS", default=True)
    photo = FileField(
        "Photo",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "gif", "webp"], "Images only.")],
    )
    remove_photo = BooleanField("Remove photo")
    submit = SubmitField("Save")
