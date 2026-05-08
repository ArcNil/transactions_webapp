from functools import wraps

from flask import abort, request
from flask_login import current_user


def superadmin_required(f):
    """Restrict a route to superadmin users only. Returns 403 for everyone else."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_superadmin:
            from app.utils.monitor import record_action
            record_action(
                user_id=current_user.id,
                username=current_user.username,
                action="security.permission_denied",
                detail=f"{request.method} {request.path}",
            )
            abort(403)
        return f(*args, **kwargs)
    return decorated
