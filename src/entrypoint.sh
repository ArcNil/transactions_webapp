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
# Skip interactive seed if the admin user already exists (avoids prompt failures without a TTY)
ADMIN_EXISTS=$(python - <<'PYEOF'
import sys
from app import create_app, db
from app.models.user import User
app = create_app()
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    print("yes" if u else "no")
PYEOF
)
if [ "$ADMIN_EXISTS" != "yes" ]; then
    flask seed
fi

echo "==> Starting server..."
exec flask run --host=0.0.0.0 --port=5000
