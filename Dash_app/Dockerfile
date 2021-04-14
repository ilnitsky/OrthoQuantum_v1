FROM tiangolo/uwsgi-nginx-flask:python3.8

RUN useradd -ms /bin/bash www                                       &&\
    apt-get update                                                  &&\
    apt-get install -y imagemagick ca-certificates build-essential    \
                       python3-lxml --no-install-recommends         &&\
    python3 -m pip install --upgrade pip                            &&\
    python3 -m pip install lxml==4.6.3                              &&\
    rm -rf ~/.cache/pip/*                                           &&\
    apt-get purge -y --auto-remove build-essential                  &&\
    rm -rf /var/lib/apt/lists/*                                     &&\
    rm -rf /usr/share/doc                                           &&\
    rm -rf /usr/share/man                                           &&\
    apt-get clean
# Installing dependencies separately in order to take advantage of docker caching mechanism

COPY ./app/requirements.txt /app/

RUN python3 -m pip install -r /app/requirements.txt                 &&\
    rm -rf ~/.cache/pip/*

COPY ./phydthree_component-0.0.1.tar.gz /app/
RUN python3 -m pip install phydthree_component-0.0.1.tar.gz         &&\
    rm -f /app/phydthree_component-0.0.1.tar.gz                     &&\
    rm -rf ~/.cache/pip/*

COPY ./nginx-site.conf /etc/nginx/conf.d/nginx.conf

COPY ./app/ /app/

RUN chown -R www:www /app/ && chown www:www /app

ENV UWSGI_CHEAPER 1
ENV UWSGI_PROCESSES 4

ENV MPLCONFIGDIR /app/matplotlib-conf/

EXPOSE 8050

WORKDIR /app/
