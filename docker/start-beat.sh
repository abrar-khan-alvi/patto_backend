#!/bin/sh
set -e

exec celery -A config beat --loglevel "${CELERY_LOG_LEVEL:-info}"
