#!/bin/bash
set -e

echo "==> Waiting for database to be ready..."
# Parse connection details from DATABASE_URL so this works with or without Compose
DB_HOST=$(python3 -c "from urllib.parse import urlparse; u=urlparse('$DATABASE_URL'); print(u.hostname)")
DB_USER=$(python3 -c "from urllib.parse import urlparse; u=urlparse('$DATABASE_URL'); print(u.username)")
DB_NAME=$(python3 -c "from urllib.parse import urlparse; u=urlparse('$DATABASE_URL'); print(u.path.lstrip('/'))")
until pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -q; do
    sleep 1
done
echo "==> Database is ready."

echo "==> Setting up database migrations..."

if [ ! -f /app/migrations/alembic.ini ]; then
    flask db init
fi

if [ ! "$(ls -A /app/migrations/versions 2>/dev/null)" ]; then
    flask db migrate -m "Initial schema"
fi

flask db upgrade

echo "==> Seeding default user..."
flask seed

echo "==> Starting server..."
# worker class, psycogreen patch, and worker-connections are declared in gunicorn.conf.py
# --worker-connections 100: conservative cap (default 1000) — 2 workers × 100 = 200 concurrent greenlets max
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --worker-connections 100 --worker-tmp-dir /dev/shm -c /app/gunicorn.conf.py main:app
