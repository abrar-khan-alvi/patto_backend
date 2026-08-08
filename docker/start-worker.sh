#!/bin/sh
set -e

exec celery -A config worker --loglevel "${CELERY_LOG_LEVEL:-info}"
