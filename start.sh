#!/bin/bash
set -e

echo "Starting SyncScope Management Service..."

# Collect static files at runtime when environment variables are available
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run database migrations (for management schema) - don't fail if they take too long
if [ "${SKIP_MIGRATE:-false}" != "true" ]; then
    echo "Running database migrations..."
    timeout 90s python manage.py migrate || echo "Migrations timed out or failed, continuing..."
else
    echo "Skipping database migrations (SKIP_MIGRATE=true)"
fi

# Start gunicorn
echo "Starting Gunicorn server..."
exec gunicorn --config gunicorn.conf.py config.wsgi:application