#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py check --deploy
python manage.py productioncheck
