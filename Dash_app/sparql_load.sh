#!/bin/sh
QUERY=$(</home/ken/best_repository_ever/Dash_app/assets/data/sample-query.sparql) &&  curl -X POST -H "Accept:application/sparql-results+json" --data-urlencode "query=$QUERY" https://sparql.orthodb.org/sparql > /home/ken/best_repository_ever/Dash_app/assets/data/json.txt
