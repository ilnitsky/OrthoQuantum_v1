#!/bin/bash
cd "$( dirname "${BASH_SOURCE[0]}" )"

echo "** Pulling from git **"
git pull
echo "** Building **"
docker-compose build
echo "** Recreating **"
docker-compose up --build -d --force-recreate
if [ ! -z "$PS1" ]; then docker-compose logs -f; fi