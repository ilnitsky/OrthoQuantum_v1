#!/bin/bash
echo "Connecting to DBs"
until timeout 3 mongosh mongodb://mongo:27017/db --quiet --eval 'exit(db.runCommand({ping: 1})["ok"] === 1 ? 0 : 1)'
do
    echo 'Retrying...'
    sleep 1
done
echo "DBs started!"

echo "Initializing the replica set (if needed)"
until timeout 60 mongosh mongodb://mongo:27017/db --quiet --file /docker-entrypoint-initdb.d/rs_init.js
do
    echo 'Retrying...'
    sleep 15
done

echo "Connecting to replica set and initializing (if needed)"
until timeout 60 mongosh mongodb://mongo:27017/db?replicaSet=rs0 --quiet --file /docker-entrypoint-initdb.d/db_init.js
do
    echo 'Retrying...'
    sleep 3
done
echo "Replica set ready!"
