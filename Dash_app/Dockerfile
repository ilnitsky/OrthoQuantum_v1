FROM buildpack-deps:buster as suexec-builder
COPY ./su-exec /su-exec
RUN cd /su-exec && make

# build phyd3 library
FROM node:15.14-slim AS phyd3-builder
USER node:node

COPY --chown=node:node phyd3/package*.json /node-app/
WORKDIR /node-app/

RUN npm install

COPY phyd3/ /node-app/

RUN node dist.js &&\
    mkdir dist/assets  &&\
    cp dist/js/*min* dist/assets/ &&\
    cp dist/css/*min* dist/assets/


# build phyd3 component for dash
FROM python:3.9-buster AS phyd3-comp-builder
# Copied from node:15.14-slim dockerfile
RUN groupadd --gid 1000 node \
  && useradd --uid 1000 --gid node --shell /bin/bash --create-home node

ENV NODE_VERSION 15.14.0

RUN ARCH= && dpkgArch="$(dpkg --print-architecture)" \
  && case "${dpkgArch##*-}" in \
    amd64) ARCH='x64';; \
    ppc64el) ARCH='ppc64le';; \
    s390x) ARCH='s390x';; \
    arm64) ARCH='arm64';; \
    armhf) ARCH='armv7l';; \
    i386) ARCH='x86';; \
    *) echo "unsupported architecture"; exit 1 ;; \
  esac \
  # gpg keys listed at https://github.com/nodejs/node#release-keys
  && set -ex \
  && for key in \
    4ED778F539E3634C779C87C6D7062848A1AB005C \
    94AE36675C464D64BAFA68DD7434390BDBE9B9C5 \
    74F12602B6F1C4E913FAA37AD3A89613643B6201 \
    71DCFD284A79C3B38668286BC97EC7A07EDE3FC1 \
    8FCCA13FEF1D0C2E91008E09770F7A9A5AE15600 \
    C4F0DFFF4E8C1A8236409D08E73BC641CC11F4C8 \
    C82FA3AE1CBEDC6BE46B9360C43CEC45C17AB93C \
    DD8F2338BAE7501E3DD5AC78C273792F7D83545D \
    A48C2BEE680E841632CD4E44F07496B3EB3C1762 \
    108F52B48DB57BB0CC439B2997B01419BD92F80A \
    B9E2F5981AA6E0CD28160D9FF13993A75599653C \
  ; do \
    gpg --batch --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys "$key" || \
    gpg --batch --keyserver hkp://ipv4.pool.sks-keyservers.net --recv-keys "$key" || \
    gpg --batch --keyserver hkp://pgp.mit.edu:80 --recv-keys "$key" ; \
  done \
  && curl -fsSLO --compressed "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-$ARCH.tar.xz" \
  && curl -fsSLO --compressed "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt.asc" \
  && gpg --batch --decrypt --output SHASUMS256.txt SHASUMS256.txt.asc \
  && grep " node-v$NODE_VERSION-linux-$ARCH.tar.xz\$" SHASUMS256.txt | sha256sum -c - \
  && tar -xJf "node-v$NODE_VERSION-linux-$ARCH.tar.xz" -C /usr/local --strip-components=1 --no-same-owner \
  && rm "node-v$NODE_VERSION-linux-$ARCH.tar.xz" SHASUMS256.txt.asc SHASUMS256.txt \
  && ln -s /usr/local/bin/node /usr/local/bin/nodejs \
  # smoke tests
  && node --version \
  && npm --version

ENV YARN_VERSION 1.22.5

RUN set -ex \
  && for key in \
    6A010C5166006599AA17F08146C2130DFD2497F5 \
  ; do \
    gpg --batch --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys "$key" || \
    gpg --batch --keyserver hkp://ipv4.pool.sks-keyservers.net --recv-keys "$key" || \
    gpg --batch --keyserver hkp://pgp.mit.edu:80 --recv-keys "$key" ; \
  done \
  && curl -fsSLO --compressed "https://yarnpkg.com/downloads/$YARN_VERSION/yarn-v$YARN_VERSION.tar.gz" \
  && curl -fsSLO --compressed "https://yarnpkg.com/downloads/$YARN_VERSION/yarn-v$YARN_VERSION.tar.gz.asc" \
  && gpg --batch --verify yarn-v$YARN_VERSION.tar.gz.asc yarn-v$YARN_VERSION.tar.gz \
  && mkdir -p /opt \
  && tar -xzf yarn-v$YARN_VERSION.tar.gz -C /opt/ \
  && ln -s /opt/yarn-v$YARN_VERSION/bin/yarn /usr/local/bin/yarn \
  && ln -s /opt/yarn-v$YARN_VERSION/bin/yarnpkg /usr/local/bin/yarnpkg \
  && rm yarn-v$YARN_VERSION.tar.gz.asc yarn-v$YARN_VERSION.tar.gz \
  # smoke test
  && yarn --version

# End of copied section

USER node:node
ENV PATH=/home/node/.local/bin:$PATH

COPY --chown=node:node phydthree_component/package*.json /phydthree_component/
WORKDIR /phydthree_component/

RUN npm install

COPY --chown=node:node phydthree_component/requirements.txt /phydthree_component/
RUN python3 -m pip --no-cache-dir install -r /phydthree_component/requirements.txt

COPY --chown=node:node phydthree_component/ /phydthree_component/

RUN npm run build  &&\
    python3 setup.py sdist bdist_wheel


FROM tiangolo/meinheld-gunicorn:python3.8

RUN useradd -ms /bin/bash -u 1234 www           &&\
    chown -R www:www /app /app/                 &&\
    apt-get update                              &&\
    apt-get upgrade -y                          &&\
    apt-get install -y --no-install-recommends    \
            ca-certificates                     &&\
    python3 -m pip --no-cache-dir                 \
            install --upgrade pip pipenv        &&\
    rm -rf /var/lib/apt/lists/*                 &&\
    rm -rf /usr/share/doc                       &&\
    rm -rf /usr/share/man                       &&\
    apt-get clean

ENV PATH=/home/www/.local/bin:$PATH

COPY --from=suexec-builder --chown=root:root /su-exec/su-exec /bin/su-exec

# Installing dependencies separately in order to take advantage of docker caching mechanism
COPY --chown=www:www ./app/Pipfile* /app/

RUN su-exec www pipenv install --deploy --system --clear

COPY --chown=www:www --from=phyd3-comp-builder \
     /phydthree_component/dist/phydthree_component-0.0.1.tar.gz /app/

RUN su www -c "python3 -m pip --no-cache-dir install phydthree_component-0.0.1.tar.gz"  &&\
    rm -f /app/phydthree_component-0.0.1.tar.gz

COPY --chown=www:www ./app/ /app/
COPY --chown=www:www --from=phyd3-builder /node-app/dist/assets/* /app/app/assets/

EXPOSE 8050

WORKDIR /app/

ENV MPLCONFIGDIR=/app/matplotlib-conf

CMD [ "" ]
ENTRYPOINT [ "/app/entrypoint.sh" ]