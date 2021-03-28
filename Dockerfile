FROM python:3.9.2-slim-buster

RUN useradd -ms /bin/bash www &&\
    mkdir -p /home/www/app &&\
    python3 -m pip install --upgrade pip

USER www
WORKDIR /home/www/app

COPY ./requirements.txt .
RUN python3 -m pip install -r ./requirements.txt

COPY ./Dash_app .

EXPOSE 8050

ENTRYPOINT ["python3", "main_app.py"]
