#/bin/sh
echo "Initializing redis server"
# overriding bind "0.0.0.0"
redis-server /usr/local/etc/redis/redis.conf --bind 127.0.0.1 >/dev/null 2>&1 &
REDIS_PID=$!

until redis-cli -e ping >/dev/null 2>&1; do
:
done

redis-cli del /scripts >/dev/null 2>&1
redis-cli script flush sync >/dev/null 2>&1

for f in /usr/local/etc/redis/scripts/*.lua ; do
    name=$(basename "$f" .lua)
    echo "Loading script \"$name\""
    hash=$(redis-cli -e --raw -x script load < "$f")
    if [ $? -eq 0 ]
    then
        redis-cli -e --raw hset /scripts $name $hash 2>&1 >/dev/null
        if [ $? -eq 0 ]
        then
            echo "Script loaded"
            continue
        fi
    fi
    echo "Failed to load script"
done
kill -SIGINT $REDIS_PID
wait $REDIS_PID >/dev/null 2>&1

redis-server /usr/local/etc/redis/redis.conf