# Reuse locally cached runtimes; no npm dependencies or image package installs.
FROM node:16.3.0-slim AS node-runtime
FROM python:3.9.5-buster
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
WORKDIR /prototype
COPY . .
ENV HOST=0.0.0.0 PORT=8051 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
EXPOSE 8051
CMD ["node", "--max-old-space-size=512", "server.mjs"]
