#!/bin/bash
set -e

echo "==> Waiting for database to be ready..."
until pg_isready -h db -U "$DATABASE_USERNAME" -d "$DATABASE_NAME" -q; do
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
