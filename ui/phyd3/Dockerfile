# build legacy phyd3 library

FROM node:16.3.0-slim
ARG DEBUG=""
ENV DEBUG=${DEBUG}
USER node:node

COPY --chown=node:node phyd3/package*.json /node-app/
WORKDIR /node-app/

RUN npm install

COPY phyd3/ /node-app/

RUN node dist.js

ENTRYPOINT [ "/bin/sh", "-c", "cp /node-app/dist/js/*min* /build && cp /node-app/dist/css/*min* /build" ]
