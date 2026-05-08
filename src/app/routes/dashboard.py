from datetime import datetime, timezone

from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app.services.dashboard_service import get_stats, get_chart_data, get_financial_summary

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@bp.route("/dashboard")
@login_required
def index():
    return render_template(
        "dashboard/index.html",
        stats=get_stats(),
        summary=get_financial_summary(),
        now=datetime.now(timezone.utc),
    )


@bp.route("/api/dashboard/chart")
@login_required
def chart_data():
    return jsonify(get_chart_data())
