FROM python:3.9.2-slim-buster

RUN useradd -ms /bin/bash www               &&\
    mkdir -p /home/www/app                  &&\
    chown www:www /home/www/app             &&\
    python3 -m pip install --upgrade pip    &&\
    apt-get update                          &&\
    apt-get install -y imagemagick          &&\
    apt-get clean

USER www
WORKDIR /home/www/app
ENV PATH="${PATH}:/home/www/.local/bin"

# Installing dependencies separately in order to take advantage of docker caching mechanism
COPY --chown=www:www ./requirements.txt .
RUN python3 -m pip install -r ./requirements.txt  &&\
    rm -rf ~/.cache/pip/*

COPY --chown=www:www ./Dash_app .

EXPOSE 8050

ENTRYPOINT ["python3", "main_app.py"]
