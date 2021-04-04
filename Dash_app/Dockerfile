# FROM python:3.9.2-slim-buster

FROM tiangolo/uwsgi-nginx-flask:python3.8

ENV LISTEN_PORT 8050
EXPOSE 8050

RUN useradd -ms /bin/nologin www                     &&\
    python3 -m pip install --upgrade pip             &&\
    rm -rf ~/.cache/pip/*                            &&\
    apt-get update                                   &&\
    apt-get install -y imagemagick ca-certificates   &&\
    apt-get clean                                    &&\
    chown -R www:www /app/                           &&\
    chown www:www /app

# Installing dependencies separately in order to take advantage of docker caching mechanism
COPY --chown=www:www ./app/requirements.txt /app/
RUN python3 -m pip install -r ./requirements.txt     &&\
    rm -rf ~/.cache/pip/*

COPY ./app/ /app/

ENV UWSGI_CHEAPER 1
ENV UWSGI_PROCESSES 4

WORKDIR /app/
