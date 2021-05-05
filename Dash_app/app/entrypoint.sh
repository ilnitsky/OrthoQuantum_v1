#! /usr/bin/env bash
set -e

ls -Ahl /app/ | grep user_data
chown -R root:root /app/user_data/
chown -R root:root /app/user_data
ls -Ahl /app/ | grep user_data
chown -R www:www /app/user_data/
chown -R www:www /app/user_data
ls -Ahl /app/ | grep user_data

# Start Gunicorn
su-exec www:www gunicorn -k egg:meinheld#gunicorn_worker -c "/app/gunicorn_conf.py" "app.main:app"