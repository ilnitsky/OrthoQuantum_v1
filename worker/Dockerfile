FROM python:3.9-slim

RUN useradd -ms /bin/bash -u 1234 www       &&\
    apt-get update                          &&\
    apt-get upgrade -y                      &&\
    apt-get install -y ca-certificates        \
                    --no-install-recommends &&\
    python3 -m pip install --upgrade pip    &&\
    python3 -m pip install pipenv           &&\
    rm -rf ~/.cache/pip/*                   &&\
    rm -rf /var/lib/apt/lists/*             &&\
    rm -rf /usr/share/doc                   &&\
    rm -rf /usr/share/man                   &&\
    apt-get clean

# Installing dependencies separately in order to take advantage of docker caching mechanism
COPY ./app/Pipfile* /app/

WORKDIR /app/

RUN pipenv install --deploy --system  &&\
    rm -rf ~/.cache/pip/*

COPY ./app/ /app/

RUN chown -R www:www /app/ && chown www:www /app

USER www
# -O fair (better for long tasks, ?)
# --prefetch-multiplier - typically long tasks, fetch 1 per worker
#   -Q, --queues COMMA SEPARATED LIST
#   -X, --exclude-queues COMMA SEPARATED LIST
CMD [ "celery", "-A", "tasks", "worker", "-l", "INFO",\
      "-Q", "celery", "--prefetch-multiplier=1", \
      "--autoscale=16,1" \
    ]
