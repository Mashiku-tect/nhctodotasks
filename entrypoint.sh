#!/bin/sh
set -e

mkdir -p /app/data /app/media /app/staticfiles

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn nhctodo.wsgi:application --bind 0.0.0.0:8000
