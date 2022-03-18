#!/bin/bash
chown -R www:www /app/user_data/
chown www:www /app/user_data
cat /app/hosts_append >>/etc/hosts
setcap 'cap_net_bind_service=+ep' /bin/proxy

runuser -u www -g www --whitelist-environment "SOCKS_SERVER,SOCKS_PORT" -- proxy &
runuser -u www -g www --whitelist-environment "REDIS_HOST,PYTHONUNBUFFERED" -- python3 -m app
