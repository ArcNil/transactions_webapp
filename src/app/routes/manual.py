from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint("manual", __name__, url_prefix="/manual")


@bp.route("/")
@login_required
def index():
    return render_template("manual/index.html")
