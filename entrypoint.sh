#!/bin/sh
set -e

<<<<<<< HEAD
mkdir -p /app/media /app/staticfiles

if [ "${DJANGO_DB_ENGINE:-sqlite}" = "mysql" ]; then
    python - <<'PY'
import os
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nhctodo.settings")

import django
from django.db import connections

django.setup()

retries = int(os.environ.get("DB_WAIT_RETRIES", "30"))
delay = float(os.environ.get("DB_WAIT_DELAY", "2"))

for attempt in range(1, retries + 1):
    try:
        connections["default"].ensure_connection()
        print("Database connection ready.")
        break
    except Exception as exc:
        if attempt == retries:
            raise
        print(f"Database not ready yet ({attempt}/{retries}): {exc}")
        time.sleep(delay)
PY
fi
=======
mkdir -p /app/data /app/media /app/staticfiles
>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222

python manage.py migrate --noinput
python manage.py collectstatic --noinput

<<<<<<< HEAD
exec "$@"
=======
exec gunicorn nhctodo.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120}
>>>>>>> 68fe5a0629c825caf0869fc3046de4b2c4bca222
