from flask import Blueprint, render_template
from flask_login import login_required
from app.services.dashboard_service import (
    get_financial_summary,
    get_sales_transactions,
    get_expense_transactions,
)
from app.utils.decorators import superadmin_required

bp = Blueprint("finance", __name__, url_prefix="/finance")


@bp.route("/")
@login_required
@superadmin_required
def index():
    return render_template(
        "finance/index.html",
        summary=get_financial_summary(),
        sales=get_sales_transactions(),
        expenses=get_expense_transactions(),
    )
