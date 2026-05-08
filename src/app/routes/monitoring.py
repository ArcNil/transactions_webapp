import json
import time

from flask import Blueprint, render_template, Response, stream_with_context
from flask_login import login_required
from app.utils.decorators import superadmin_required
from app.utils.monitor import get_stats

bp = Blueprint("monitoring", __name__, url_prefix="/monitoring")


@bp.route("/")
@login_required
@superadmin_required
def index():
    stats = get_stats()
    return render_template("monitoring/index.html", stats=stats)


@bp.route("/stream")
@login_required
@superadmin_required
def stream():
    """SSE endpoint — pushes a fresh stats snapshot every 3 seconds."""
    def generate():
        while True:
            data = json.dumps(get_stats())
            yield f"data: {data}\n\n"
            time.sleep(3)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering if behind a proxy
        },
    )
