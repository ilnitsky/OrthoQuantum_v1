#!/bin/bash
chown -R www:www /app/user_data/
chown www:www /app/user_data

exec su-exec www:www python3 -m app
