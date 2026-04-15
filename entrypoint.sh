#!/bin/sh
set -e

mkdir -p /app/media /app/staticfiles

if [ "${DJANGO_DB_ENGINE:-sqlite}" = "mysql" ]; then
    retries="${DB_WAIT_RETRIES:-30}"
    delay="${DB_WAIT_DELAY:-2}"
    attempt=1

    while [ "$attempt" -le "$retries" ]; do
        if python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nhctodo.settings'); import django; django.setup(); from django.db import connections; connections['default'].ensure_connection()"; then
            echo "Database connection ready."
            break
        fi

        if [ "$attempt" -eq "$retries" ]; then
            echo "Database connection failed after ${retries} attempts."
            exit 1
        fi

        echo "Database not ready yet (${attempt}/${retries})."
        attempt=$((attempt + 1))
        sleep "$delay"
    done
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec gunicorn nhctodo.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}"
