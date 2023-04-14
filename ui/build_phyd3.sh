#!/bin/bash
cd "$( dirname "${BASH_SOURCE[0]}" )"
rm -rf static/phyd3*
docker build -t phyd3_builder ./phyd3
docker run --rm -v $PWD/static:/build phyd3_builder
