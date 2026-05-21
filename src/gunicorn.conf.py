# Gunicorn configuration file
# Applied via: gunicorn -c /app/gunicorn.conf.py ...

# Declare worker class here so this file is self-contained — the post_fork hook
# below is only safe under gevent; co-locating the setting makes that obvious.
worker_class = "gevent"


def post_fork(server, worker):
    """Patch psycopg2 to use gevent-cooperative sockets after each worker forks.

    Without this, psycopg2 uses libpq's C-level blocking socket calls that
    bypass gevent's monkey-patch, causing DB operations to block the OS thread
    instead of yielding cooperatively to other greenlets.
    """
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()
