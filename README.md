# OrthoQuantum

The main application is the lightweight JavaScript/Canvas interface in [`web/`](web/README.md).
It uses a Node HTTP server and a read-only Python/SQLite adapter, with no npm runtime
dependencies or Dash/Redis analysis queue. The main deployment uses **127.0.0.1:8050**.

```bash
# Build/restart the main application, retaining the existing lightweight deployment identity.
./compose.sh up -d --build
./compose.sh logs --tail=50 lite xray-relay
# Equivalent rebuild shortcut:
./rebuild.sh
```

`compose.sh` always selects project `orthoquantum_lite` and the root Compose file.
It supports the Docker Compose plugin or legacy `docker-compose`. This keeps the
main application separate from the older Dash project's containers and volumes.
Use this wrapper rather than an unqualified `docker-compose up` on this host.

For direct development with Node 18+ and Python 3.9+:

```bash
ORTHODB_PROXY=socks5h://127.0.0.1:10808 PORT=8050 node web/server.mjs
# Optional Docker source bind, on the main service:
./compose.sh -f docker-compose.test.yml up -d --build
```

The existing site proxy can continue targeting port 8050. Legacy Dash is available
on loopback 8051. `ORTHOQUANTUM_PUBLIC_ORIGINS` configures accepted public origins
(default: HTTP and HTTPS for `orthoq.bioinf.fbb.msu.ru`).

The read-only reference mount defaults to `/home/ilnitsky/PANTHERDB`; override
`ORTHOQUANTUM_REFERENCE_DIR` if needed. `ORTHOQUANTUM_PORT` overrides host port 8050.
The main stack's Xray relay uses Docker gateway port **10810**, forwarding to host
loopback **10808**. The legacy stack's existing relay remains on 10809. Override
`LITE_ORTHODB_PROXY` to use another proxy or set it empty to disable proxying.

The configured OrthoDB release remains **v11** while the separately built v13
candidate is validated. Never change only the database file without aligning
IDs, demos, endpoints and caches. A validated PANTHER v19 bundle is selected with
its matching tree/map; incomplete bundles remain unavailable.

## Branches and legacy application

- `snapshot/dash-and-lite`: preserves all current Dash improvements, the 8051
  implementation and database build/repair tooling before promotion.
- `main/lightweight`: derives from that snapshot and makes `web/` the main app.

The older Dash implementation remains in `dash_app/`, `worker/` and `redis/`.
Its deployment is preserved in `docker-compose.legacy.yml`; its development
configuration is `docker-compose.legacy-test.yml`. On this host, the existing Dash
service runs on 8051. To manage it deliberately:

```bash
docker-compose -p best_repository_ever -f docker-compose.legacy.yml ps
# Rebuild only if deliberately deploying legacy Dash:
./rebuild-legacy.sh
```

No legacy Redis or user-result volumes are removed. Database builds are independent
detached containers and are not restarted by the main application's Compose commands.

## Checks and limits

```bash
node --test web/tests/*.test.mjs
python3 -m unittest discover -s web/tests -p 'test_*.py' -v
```

See [`web/VALIDATION.md`](web/VALIDATION.md) for browser checks and
[`web/README.md`](web/README.md) for features and scientific limits. Branches show
**topology only**; correlations/clustering cover the first 160 groups; BLAST is
unavailable. JSON/CSV downloads and full SVG export are supported. Browser history
retains 15 datasets and displays the newest 10; legacy Redis sessions are not migrated.

The Dockerfile retains the previously tested cached Node 16/Python 3.9 image
combination during this code promotion. Those legacy runtimes require a separate
upgrade before treating this as an internet-facing production deployment. The
service remains bound to loopback with a read-only root/reference mount.

Database tooling and status commands are in [`support_scripts/orthodb/README.md`](support_scripts/orthodb/README.md)
and [`support_scripts/panther/README.md`](support_scripts/panther/README.md).
