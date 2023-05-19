FROM node:latest
ARG DEBUG=""
ENV DEBUG=${DEBUG}
RUN npm install -g json
USER node:node

COPY --chown=node:node /package*.json /node-app/
WORKDIR /node-app/

RUN npm install &&\
    # hack for popper to play nicely with vite
    json -I -f node_modules/@popperjs/core/package.json -e 'this.type="module"'

COPY --chown=node:node / /node-app/

RUN npm run serde && npm run build

CMD [ "node", "./prod_server.js" ]