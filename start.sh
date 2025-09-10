#!/bin/bash
set -e

# Collect static files at runtime when environment variables are available
python manage.py collectstatic --noinput

# Run database migrations (for management schema) - don't fail if they take too long
if [ "${SKIP_MIGRATE:-false}" != "true" ]; then
    echo "Running database migrations..."
    timeout 60s python manage.py migrate || echo "Migrations timed out or failed, continuing..."
fi

# Start gunicorn
exec gunicorn --config gunicorn.conf.py config.wsgi:application