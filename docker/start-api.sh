#!/bin/sh
set -e

python manage.py collectstatic --noinput
exec gunicorn config.asgi:application \
  --bind 0.0.0.0:8000 \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "${WEB_CONCURRENCY:-2}" \
  --access-logfile - \
  --error-logfile -
