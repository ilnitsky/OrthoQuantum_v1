#!/bin/bash
set -e

docker build -t phyd3_builder phyd3
CONT=$(docker create --name phyd3_builder phyd3_builder)
docker cp "$CONT:/node-app/dist/phyd3.min.css" ./ui/static/
docker cp "$CONT:/node-app/dist/phyd3.min.js" ./ui/static/
docker rm "$CONT"
