#!/bin/bash
chown -R www:www /app/user_data/
chown www:www /app/user_data

# Proxy stuff
cat /app/hosts_append >>/etc/hosts

setcap 'cap_net_bind_service=+ep' /bin/proxy
if [ $? -eq 0 ]; then
    runuser -u www -g www --whitelist-environment "SOCKS_SERVER,SOCKS_PORT" -- proxy &
else
    # failed with setcap, have to run as root
    proxy &
fi
runuser -u www -g www --whitelist-environment "REDIS_HOST,PYTHONUNBUFFERED" -- python3 -m app
