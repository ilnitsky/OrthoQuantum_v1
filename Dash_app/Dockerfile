FROM python:3.9.2-slim-buster

RUN useradd -ms /bin/bash www               &&\
    mkdir -p /home/www/app                  &&\
    chown www:www /home/www/app             &&\
    python3 -m pip install --upgrade pip    &&\
    rm -rf ~/.cache/pip/*                   &&\
    apt-get update                          &&\
    apt-get install -y imagemagick          &&\
    apt-get clean

USER www
WORKDIR /home/www/app
# allows using flask as a command
ENV PATH="${PATH}:/home/www/.local/bin"

# Installing dependencies separately in order to take advantage of docker caching mechanism
COPY --chown=www:www ./requirements.txt .
RUN python3 -m pip install -r ./requirements.txt  &&\
    rm -rf ~/.cache/pip/*

COPY --chown=www:www . .

EXPOSE 8050

ENTRYPOINT ["flask", "run", "--host=0.0.0.0", "--port=8050"]
