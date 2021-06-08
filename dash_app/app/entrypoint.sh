#! /usr/bin/env bash
set -e

chown -R www:www /app/user_data/
chown www:www /app/user_data

# Start Gunicorn
exec su-exec www:www gunicorn -k egg:meinheld#gunicorn_worker -c "/app/gunicorn_conf.py" "app.main:app"