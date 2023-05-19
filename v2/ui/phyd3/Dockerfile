FROM node:16.3.0-slim
ARG DEBUG=""
ENV DEBUG=${DEBUG}

USER node:node

COPY --chown=node:node ./package*.json /node-app/
WORKDIR /node-app/

RUN npm install

COPY / /node-app/

RUN node dist.js
# artifacts are at /node-app/dist/phyd3.min.{css,js}
ENTRYPOINT [ "/bin/bash" ]