#!/bin/bash
chown -R www:www /app/user_data/
chown www:www /app/user_data


# -O fair (better for long tasks, ?)
# --prefetch-multiplier - typically long tasks, fetch 1 per worker
#   -Q, --queues COMMA SEPARATED LIST
#   -X, --exclude-queues COMMA SEPARATED LIST

su-exec www:www python3 -m app
# celery -A tasks worker -l INFO -Q celery --prefetch-multiplier=1 --autoscale=16,1