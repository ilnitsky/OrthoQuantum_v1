FROM mongo:6

COPY db_init /docker-entrypoint-initdb.d

COPY ./docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh