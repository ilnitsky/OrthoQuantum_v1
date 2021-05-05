#!/bin/bash
ls -Ahl /app/ | grep user_data
chown -R root:root /app/user_data/
chown -R root:root /app/user_data
ls -Ahl /app/ | grep user_data
chown -R www:www /app/user_data/
chown -R www:www /app/user_data
ls -Ahl /app/ | grep user_data

su-exec www:www celery -A tasks worker -l INFO -Q celery --prefetch-multiplier=1 --autoscale=16,1