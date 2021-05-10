FROM buildpack-deps:buster as suexec-builder
COPY ./su-exec /su-exec
RUN cd /su-exec && make

FROM python:3.9-slim
ARG DEBUG=""
ENV DEBUG=${DEBUG}

RUN useradd -ms /bin/bash -u 1234 www           &&\
    apt-get update                              &&\
    apt-get upgrade -y                          &&\
    apt-get install -y --no-install-recommends    \
            ca-certificates build-essential     &&\
    python3 -m pip --no-cache-dir                 \
            install --upgrade pip pipenv        &&\
    rm -rf /var/lib/apt/lists/*                 &&\
    rm -rf /usr/share/doc                       &&\
    rm -rf /usr/share/man                       &&\
    apt-get clean

ENV PATH=/home/www/.local/bin:$PATH

COPY --from=suexec-builder --chown=root:root /su-exec/su-exec /bin/su-exec

WORKDIR /app/

# Installing dependencies separately in order to take advantage of docker caching mechanism
COPY --chown=www:www ./app/Pipfile* /app/
RUN su www -c "pipenv install --deploy --system --clear"

COPY --chown=www:www ./app/ /app/

# entrypoint.sh drops the priveleges as soon as it
# ensures correct permissions on everything
ENTRYPOINT [ "/app/entrypoint.sh" ]
