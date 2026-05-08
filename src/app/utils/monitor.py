"""
In-memory monitoring store.

Holds ring buffers for recent HTTP requests and business actions,
tracks currently active sessions, and reads live system resources
via psutil. All state resets on container restart — this is intentional
(live view only, no persistence needed).
"""

import threading
from collections import deque
from datetime import datetime, timezone

import psutil

_MAX_ENTRIES = 50

_lock = threading.Lock()

# deque[dict] — most-recent entry at the right
_request_log: deque = deque(maxlen=_MAX_ENTRIES)
_action_log: deque = deque(maxlen=_MAX_ENTRIES)

# {user_id: {"username": str, "ip": str, "login_at": str}}
_active_sessions: dict = {}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ── Public write API ──────────────────────────────────────────────────────────

def record_request(ip: str, method: str, path: str, user_id, username: str, status_code: int) -> None:
    entry = {
        "ts": _now(),
        "ip": ip,
        "method": method,
        "path": path,
        "user_id": user_id,
        "username": username or "—",
        "status": status_code,
    }
    with _lock:
        _request_log.append(entry)


def record_action(user_id, username: str, action: str, detail: str = "") -> None:
    entry = {
        "ts": _now(),
        "user_id": user_id,
        "username": username or "—",
        "action": action,
        "detail": detail,
    }
    with _lock:
        _action_log.append(entry)


def session_opened(user_id, username: str, ip: str) -> None:
    with _lock:
        _active_sessions[user_id] = {
            "username": username,
            "ip": ip,
            "login_at": _now(),
        }


def session_closed(user_id) -> None:
    with _lock:
        _active_sessions.pop(user_id, None)


# ── Public read API ───────────────────────────────────────────────────────────

def get_stats() -> dict:
    """Return a snapshot of all monitoring data for the template."""
    with _lock:
        requests = list(reversed(_request_log))
        actions = list(reversed(_action_log))
        sessions = dict(_active_sessions)

    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    resources = {
        "cpu_pct": cpu,
        "mem_pct": mem.percent,
        "mem_used_mb": mem.used // (1024 * 1024),
        "mem_total_mb": mem.total // (1024 * 1024),
        "disk_pct": disk.percent,
        "disk_used_gb": disk.used // (1024 ** 3),
        "disk_total_gb": disk.total // (1024 ** 3),
    }

    return {
        "resources": resources,
        "active_sessions": sessions,
        "requests": requests,
        "actions": actions,
    }
