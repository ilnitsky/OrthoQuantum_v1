# Current branch: main/lightweight

The main application is now `web/` (vanilla JavaScript/Canvas, Node HTTP server,
read-only Python SQLite adapter). The root `docker-compose.yml` starts that app
on loopback 8050 with its own Xray relay on 10810. Use `./compose.sh` to retain
project `orthoquantum_lite`; `./rebuild.sh` rebuilds only that project. The existing
Dash deployment on 8051 is preserved in `docker-compose.legacy.yml`, with legacy
development config `docker-compose.legacy-test.yml`. No automatic database or
Redis-session migration occurs. See README.md and web/README.md for current run
commands and scientific limits. `snapshot/dash-and-lite` preserves the parent
snapshot before this promotion.

Validate main changes with `node --test web/tests/*.test.mjs` and
`python3 -m unittest discover -s web/tests -p 'test_*.py' -v`; browser checks are
in `web/tests/browser.smoke.mjs`. Keep reference files read-only and do not move
or restart detached database builders when restructuring frontend code.

The following detailed project guide documents legacy Dash modules and data
tooling retained on this branch; its deployment commands explicitly use the
legacy Compose files. Main-app defaults are described above.

# Project guide

PANTHER v19 candidate tooling is in `support_scripts/panther/`: `build_v19.py`
downloads and validates a separate bundle, `relations.go` streams normalized
ortholog/paralog pairs, and `tree_assets.py` builds matching tree/ID assets.
See its README for commands. The database, species tree, ID map and
release-specific caches must agree before a production migration.

See [PROGRESS.md](PROGRESS.md) for the November 2026 interface/backend change
record, affected files, commented operational commands and v13 build snapshot.

The main JavaScript/Canvas application is under
[`web/`](web/README.md).
It uses its own `orthoquantum_lite` Compose project and loopback port 8050;
the retained legacy Dash deployment is now on 8051. Its Node server/Python standard-library adapter reads
reference databases only, without production Redis/session/queue access. See its
README and VALIDATION.md for tests, measured draw times and scientific limitations.

## What this project does

This repository contains **OrthoQuantum**, a bioinformatics web application for
looking up genes/proteins and orthologous groups, comparing their presence across
species, and displaying phylogenetic trees and correlation heatmaps. It combines
Flask/Dash, a custom React/PhyD3 tree viewer, Python background jobs, Redis, local
SQLite reference databases, and external biological data services.

This guide describes the source in this checkout. Running containers can contain
older builds; their age and status do not establish which source is deployed.

## Architecture and Docker services

| Compose service | Purpose | Network/storage |
| --- | --- | --- |
| `web` | Flask/Dash UI served by Gunicorn with the Meinheld worker | Legacy binds host `127.0.0.1:8051` to container port 8050; shares `/app/user_data` with worker |
| `worker` | Async Redis queue consumer; queries reference data and generates analysis files | Uses Redis and the Xray relay; mounts reference databases and shared results |
| `redis` | Sessions/task metadata, job streams, progress updates, cache, and Lua scripts | Redis 6.2 Alpine; AOF enabled; persistent `/data`; no published host port |
| `xray-relay` | Forwards the worker SOCKS connection to host Xray at `127.0.0.1:10808` | Reuses the worker image with host networking; binds Docker gateway `172.17.0.1:10809` |

The supplied `docker ps` output maps `best_repository_ever_web_1`,
`best_repository_ever_worker_1` and `best_repository_ever_redis_1` to the
application services. The Xray relay is `best_repository_ever_xray-relay_1`. The containers named
`sharelatex`, `mongo`, and `redis` are not defined by this repository's Compose
files. The reported Mongo restart loop is outside this application's stack;
OrthoQuantum uses Redis and SQLite, not MongoDB.

Typical flow:

1. The UI records a request and enqueues an analysis stage in Redis.
2. Worker handlers resolve identifiers/orthogroups using local SQLite data and
   OrthoDB/UniProt services, then build tables, trees, and heatmaps.
3. Optional BLAST jobs query NCBI and add similarity results to the tree.
4. Worker files go into shared `user_data`; the UI polls Redis for state changes
   and serves generated files through Flask routes.

## Root files and deployment

| File | Role |
| --- | --- |
| `docker-compose.legacy.yml` | Production stack, restart policies, required environment, named volumes, and host reference-data mounts |
| `docker-compose.legacy-test.yml` | Separate development configuration: DEBUG build arguments, host port 8050, worker port 5678, bind-mounted results/reference data; it does not itself run a test suite |
| `rebuild.sh` | Changes to repository directory, runs `git pull`, builds images, and force-recreates Compose containers; optionally follows logs when `PS1` is set. It has no `set -e`, so a failed step can be followed by another step |
| `.env` and local variants | Deployment configuration/secrets; never copy values into documentation, logs, or commits |
| `.python-version`, `.pylintrc`, `.gitignore`, `.dockerignore` | Local Python/tooling and ignore configuration; Dockerfiles explicitly build Python 3.9.5 runtimes |
| `default_for_chrome.json` | Chrome-oriented seccomp profile; references in Compose are currently commented out |
| `index.html` | Saved Dash HTML shell; Compose runs the Python app, not this root HTML file |
| `manual_svg_render_prototype/t.html` | Standalone SVG rendering experiment |

Production requires `SECRET_KEY` and `DEMO_TID`. Host Xray must provide SOCKS5
on `127.0.0.1:10808`; `XRAY_RELAY_BIND` optionally overrides the Docker gateway
address (default `172.17.0.1`). Docker 20.10+ provides the worker host-gateway alias.
`DEMO_TID` identifies a saved demo task. If its result directory or saved tree state
is unavailable, the demo button queues a bundled four-protein example instead.
Worker environment
also supplies `REDIS_HOST`, `SOCKS_SERVER`, and `SOCKS_PORT`.

Production mounts `/home/ilnitsky/nr` at `/blast/blastdb` and
`/home/ilnitsky/PANTHERDB` at `/PANTHERDB`. Code expects at least
`/PANTHERDB/orthodb.db` and `/PANTHERDB/panther.sqlite`. These large external
databases are not built by application startup. Named volumes `user_data_v2` and
`redis_data_v2` preserve results and Redis data. Development instead uses
`./user_data`, `./blast_data`, `./pantherdb`, and a separate Redis named volume.

Useful commands from the repository root (the existing helper uses legacy
`docker-compose`; use `docker compose` where the Compose plugin is installed):

```sh
docker compose -f docker-compose.legacy.yml ps
docker compose -f docker-compose.legacy.yml logs --tail=100 web worker redis xray-relay
docker compose -f docker-compose.legacy.yml build
docker compose -f docker-compose.legacy.yml up -d
docker compose -f docker-compose.legacy-test.yml up --build -d
```

The retained legacy development configuration publishes 8050; choose another
port before running it alongside the lightweight main application. Building/recreating services changes deployment state. Do not use
`rebuild.sh` merely to inspect the project, and do not remove persistent volumes
as a troubleshooting shortcut.

## Web application scripts

Paths in this table are relative to `dash_app/`.

| Path | What it does |
| --- | --- |
| `Dockerfile` | Builds `su-exec`, bundles PhyD3 assets, builds/packages the custom Dash component, installs locked Python dependencies, and assembles the web image |
| `app/entrypoint.sh` | Fixes result-directory ownership and uses `su-exec` to start Gunicorn as `www` |
| `app/gunicorn_conf.py` | Binds 8050, configures four workers, logging, preloading, and request/shutdown timeouts |
| `app/app/main.py` | Creates Flask and Dash apps, configures compression and sessions, routes pages, handles form callbacks and analysis settings, queues/cancels work, polls progress, and serves `/files/<task_id>/<name>` and `/prottree/<name>` |
| `app/app/layout/layout.py` | Dash page layouts, controls, tables, modals, tutorial UI, and display defaults |
| `app/app/user.py` | Session/user registration and synchronous Redis access; task enqueue/cancel, queue positions, and versioned state updates through Lua. At import it waits for the worker readiness marker |
| `app/app/query_titles.py` | Input-based automatic query titles with stable query numbers; preserve explicit custom names. Legacy default names update when opened or listed |
| `app/app/utils.py` | Dash callback proxy helpers, parsing/clamping, integer decoding, and DEBUG flag |
| `app/ssr/index.html` | Browser page intended for worker-driven server rendering |
| `app/app/assets/` | Application CSS and tutorial images; image build also copies bundled PhyD3 assets here |
| `app/app/assets/fonts/` | Locally served JetBrainsMono Nerd Font regular/bold and license notices; the shared family covers text controls, tables and interactive SVG labels |
| `app/Pipfile`, `app/Pipfile.lock` | Web Python dependencies and deployment lock |
| `su-exec/su-exec.c`, `su-exec/Makefile` | Vendored privilege-dropping executable and its build recipe |

`app` is the Flask WSGI application; `dash_app` is its Dash interface. Both web
and worker use packages named `app`, rooted in their respective container `/app`
directories. Avoid mixing their import paths when running tools locally.

## Worker scripts and modules

Paths below are relative to `worker/`.

| Path | What it does |
| --- | --- |
| `Dockerfile` | Builds Go proxy, adds Python 3.9.5 to an NCBI BLAST image, installs locked dependencies, and copies worker code/reference trees |
| `app/entrypoint.sh` | Fixes shared-directory ownership, appends proxy host mappings, starts proxy with low-port capability (or root fallback), then runs `python3 -m app` as `www` |
| `app/hosts_append` | Hostname overrides used to route selected outbound requests through the local proxy |
| `app/app/__main__.py` | Initializes Redis/reference levels, publishes `/worker_initialied` readiness marker, runs queue listener and cache maintenance; removes readiness marker on exit |
| `app/app/redis/db.py` | Async text/binary Redis clients, Lua wrappers, queue acknowledgements, and startup registration of species/tree levels from SQLite and phyloXML |
| `app/app/db.py` | Synchronous Redis client and OrthoDB database path used by blocking helpers |
| `app/app/task_manager/queue_manager.py` | Registers handlers, consumes Redis streams, limits concurrency, handles cancellation/recovery, and finishes/acknowledges jobs |
| `app/app/task_manager/db_client.py` | Per-job context, guarded Redis transactions, task state/progress reporting, error handling, and file publication |
| `app/app/task_manager/exceptions.py` | Exceptions for superseded jobs and reported failures |
| `app/app/async_executor/async_executor.py` | Thread/process pools with per-function concurrency limits and queue-position progress futures |
| `app/app/utils/utils.py` | Atomic file replacement, file opening, retry/backoff utilities, benchmarking, JSON/integer helpers, data path and DEBUG flag |
| `app/app/tasks/__init__.py` | Imports active task modules to register handlers; `blast_original.py` is not imported here |
| `app/Pipfile`, `app/Pipfile.lock` | Worker dependencies and lockfile |

Task modules under `worker/app/app/tasks/`:

| Module | Responsibility |
| --- | --- |
| `table.py` | `/queues/table`: resolve gene/protein inputs, retrieve orthogroups and annotations, prepare result tables and downstream analysis |
| `table_sync.py` | Blocking SQLite identifier/orthogroup lookups, UniProt/OrthoDB requests, versioned REST metadata retrieval, CSV processing, and dataframe persistence |
| `orthodb_metadata.py` | Fetch matching v11 `/group` annotations, preserve missing optional fields, and reject mismatched group IDs; metadata cache is isolated under `/cache/ortho/v11-group` |
| `vis.py` | `/queues/vis` and `/queues/tree_csv`: coordinate tree/heatmap generation and tree-data CSV export |
| `vis_sync.py` | Read species data from XML, normalize/prepare correlation input, and export tree data to CSV |
| `profile_data.py` | Restrict membership rows to selected species before joining gene annotations; use a connection-local TEMP filter, retain legacy taxonomy aliases and distinct-gene counts |
| `tree_heatmap.py` | Async orchestration and cache handling for heatmaps and annotated species trees; called by analysis tasks, not independently registered as a queue handler |
| `tree_heatmap_sync.py` | Process-pool computation of correlations/plots and phyloXML annotations |
| `blast.py` | Active `/queues/blast` handler (up to three jobs): submit/poll NCBI web BLAST, manage retries and cached taxonomy/results, filter matches, and update analysis |
| `blast_sync.py` | Load XML/orthogroup data, identify missing matches, and process BLAST data in executor helpers |
| `blast_original.py` | Alternative older `/queues/blast` implementation using local `blastp`; not loaded by the normal task initializer. Do not import alongside the active handler without deciding which should own the queue |
| `prottree.py` | `/queues/prottree`: generate protein/subfamily trees into `user_data/prottrees` and report progress |
| `prottree_sync.py` | Query `panther.sqlite`, group/filter subfamilies, and build annotated PANTHER XML trees in a process pool |
| `ssr.py` | `/queues/ssr`: manage a Pyppeteer browser/page pool and export tree PNG/SVG images |

Cache maintenance runs every two hours, expiring entries after roughly three
months without access or six months total and requesting Redis AOF compaction.
Preserve the existing Redis key names, including misspellings such as
`/worker_initialied` and `/availible_levels`, unless migrating every consumer.

### Outbound Go proxy

`worker/proxy/main.go` listens on worker loopback ports 80/443. It reads HTTP Host
or TLS SNI and forwards traffic through the configured SOCKS5 endpoint without
terminating the remote TLS session. `enableDebug.go` enables diagnostic logging
with build tag `enableDebug`; `disableDebug.go` supplies the default false flag.
`go.mod`/`go.sum` define its dependencies.

## Redis startup and Lua scripts

`redis/Dockerfile` copies configuration/scripts into Redis 6.2 Alpine.
`redis/start.sh` starts a temporary loopback server, clears the script registry
and Lua cache, loads each Lua file, records its SHA in `/scripts`, stops that
server, and starts Redis with `redis/cfg/redis.conf`. Application clients use
`EVALSHA`, so Redis startup is part of application initialization.

| Script in `redis/cfg/scripts/` | Purpose |
| --- | --- |
| `enqueue.lua` | Atomically replace/enqueue stage work and notify cancellation of superseded jobs |
| `launch.lua` | Move a matching stage from enqueued to running; recognize recovery of the same job |
| `finish.lua` | Clear the matching running/enqueued stage without clearing newer work |
| `get_queue_pos.lua` | Estimate a job's position from stream consumer-group delivery state |
| `send_updates.lua` | Advance task-state versions and track changed keys, including connection-specific handling |
| `get_updates.lua` | Return changes since a connected client's last version |
| `get_updates_new_connection.lua` | Initialize connection tracking and return initial state |
| `happend.lua` | Append text to a Redis hash field with an optional separator |

## Tree viewer and component tooling

`dash_app/phyd3/` contains the PhyD3 viewer and bundled dependencies. The primary
viewer sources are `js/phyd3.phyloXML.js` (XML parsing), `js/phyd3.newick.js`
(Newick parsing), and `js/phyd3.phylogram.js` (tree rendering/interactions).
`dist.js` bundles/minifies JavaScript and CSS into `dist/`; `DEBUG` disables
compression. `phyd3.js` is the standalone Node static-serving entry point.
The PHP `fetch.php`, `submit.php`, and `view.php` implement the upstream
submission/conversion/viewing pages; the production web image does not run PHP.
`dist-example/`, documentation, fonts, images, and third-party minified scripts
support the upstream viewer/demo. Preserve license notices.

`dash_app/phydthree_component/` wraps the viewer for Dash:

- `src/lib/components/PhydthreeComponent.react.js`: editable React component.
- `src/lib/index.js`: JavaScript exports; `src/demo/`: development demo.
- `webpack.config.js`, `webpack.serve.config.js`: bundle and demo-server settings.
- `usage.py`: standalone Dash viewer example serving `vertebrata.xml`.
- `setup.py`, `MANIFEST.in`: Python distribution packaging.
- `_validate_init.py`: package-initializer validation used before npm publishing.
- `phydthree_component/`, `deps/`, `inst/deps/`, `R/`, `man/`,
  `src/phydthreecomponent.jl`: generated bundles/metadata and language bindings;
  prefer source edits followed by regeneration.

Package commands, run inside that component directory:

| Command | Purpose |
| --- | --- |
| `npm start` | Run Webpack demo server |
| `npm run build:js` | Build production JS bundle |
| `npm run build:backends` | Generate Dash Python/R/Julia bindings and metadata |
| `npm run build` | Run both builds; used by the Dockerfile |
| `npm run validate-init` | Check Python package initializer; also run by `prepublishOnly` |
| `npm run build:backends-activated`, `npm run build:activated` | Legacy virtualenv convenience commands; currently reference missing `build:py_and_r`, so inspect/fix before relying on them |

The `support_scripts/xray_relay.py` TCP relay preserves SOCKS traffic and forwards
it to host loopback. Compose reuses image `best_repository_ever_worker`; on a fresh
checkout build the worker image before starting the relay. The relay overrides
the worker entrypoint, so it does not run analysis jobs.

## Data preparation utilities

| Path | Purpose |
| --- | --- |
| `worker/converter/newick_to_xml.py` | Converts configured Newick species trees to colored phyloXML, resolves taxonomy through SPARQL, and generates PANTHER tree/ID mapping files. Its `main()` writes multiple configured outputs; inspect paths before running |
| `worker/converter/prottree_species_data.py` | Static PANTHER genome-code to species-name mapping used by the converter |
| `worker/converter/newick/` | Source Newick trees |
| `worker/converter/panther/` | PANTHER conversion inputs/outputs; runtime copies live separately under `worker/app/panther/` |
| `worker/app/phyloxml/` | Runtime species-tree templates; numeric filename prefixes and level names are parsed at worker startup |
| `support_scripts/generate_panther_sqlite_db.sql` | SQLite CLI script importing `PTHRfull.txt`, splitting compound fields, normalizing empty fields, and indexing the `panther` table |
| `support_scripts/orthodb/tab_2_sqlite_importer/main.go` | CLI preprocessing of `gene_xrefs`, `gene_names`, or `OG2genes` tab files; packs OrthoDB identifiers into integers and filters data for import |
| `support_scripts/orthodb/download_v13.py` | Resume and MD5-verify required compressed v13 reference tables through Xray; does not migrate the live app/database; see adjacent `README.md` |
| `support_scripts/orthodb/stream_v13.go`, `build_v13.py` | Stream verified v13 archives into a separate SQLite candidate with the reference schema; preserve live DB; report checks/timings in a sidecar |
| `support_scripts/orthodb/repair_v13_mappings.py`, `test_repair_v13.py` | Repair the fully loaded but unpublished v13 candidate from dedicated gene xrefs, preserve memberships, replace genes/indexes transactionally, validate before publishing; detached job is `orthodb-v13-mapping-repair` |
| `support_scripts/orthodb/complete_v13_symbols.py` | Reuse completed v13 aliases, resolve dedicated NCBI GeneIDs through daily NCBI gene_info with exact taxid agreement, and validate a separate symbols file before atomic candidate repair; live DB stays read-only |
| `support_scripts/orthodb/scripts/tabprocessor` | Prebuilt executable associated with that Go importer; source is the editable reference |
| `support_scripts/orthodb/scripts/1_uniprot.sql` | Import OrthoDB-to-UniProt mappings and index them |
| `support_scripts/orthodb/scripts/2_gene_names.sql` | Import names, merge mappings into `genes`, and build lookup indexes |
| `support_scripts/orthodb/scripts/3_OG.sql` | Import orthogroup membership and populate supported taxonomy `levels` |
| `support_scripts/orthodb/*.tab` | Large local reference inputs; some are untracked |
| `test_data/*.csv` | Example protein input files for manual analysis checks |
| `blast_data/` | Development BLAST database mount directory |

The Go importer writes a **FIFO** at `/tmp/import_data.tab`, not a regular output
file. Run the corresponding SQLite CLI import concurrently in another process
sharing that filesystem; otherwise it waits for a reader. Perform the three
imports in numbered order, with matching input versions, against a prepared
database copy. SQL scripts create/drop tables and are not safe idempotent
migrations. The repository mixes older input filenames and newer OrthoDB API
versions; verify compatibility rather than assuming all datasets match.

## Working on this repository

### OrthoDB release audit

Search uses `data.orthodb.org/v11/search`. A live AGO1 check matched local
`Q9UL18` / gene `9606_0:000127` to v11 group `3060088at2759` at level 2759.
The local SQLite database has no release metadata, so this verifies that example,
not the provenance of the whole database. Metadata now uses the versioned v11
`/group` API. It previously used an unversioned SPARQL endpoint, whose release
could differ. Never reuse metadata caches across releases or providers.
Group download links generated in `table.py` now target the v11 FASTA endpoint;
previously persisted task tables may retain older links until regenerated.
The unused `get_gene_name()` helper and sequence fallback in `table_sync.py`
still reference v10.1 and need review before a full release alignment.

- Read the relevant web callback, worker handler, and Lua wrapper together when
  changing task state. Keep queue names, stage versions, cancellation behavior,
  and result filenames consistent across services.
- Keep blocking network/SQLite work and CPU-heavy plotting out of the async event
  loop; use the existing thread/process executor patterns.
- Preserve atomic publication of result files so web requests cannot read partial
  outputs. Keep user/task file access checks intact.
- Respect existing local changes. Do not commit secrets, generated user results,
  reference databases, large tab inputs, or incidental build artifacts.
- The Dockerfiles use old pinned runtimes and external package/key servers.
  Dependency upgrades require a deliberate compatibility check with Dash,
  aioredis/AnyIO, the generated component, and external data APIs.
- Web startup waits for worker initialization; if it stalls, inspect worker and
  Redis logs and confirm reference databases/tree levels before treating it as
  a UI problem. Compose does not declare service health checks/dependencies.
- SSR currently navigates to `/some_non_public_ssr_path`, but its Flask route in
  `main.py` is commented out. Confirm route and browser availability before
  expecting server-rendered exports to work.

## Validation

Run `python3 -m unittest discover -s dash_app/app/tests -v` for demo-loading
regressions (missing files/state, fallback enqueue, and snapshot ownership) and
automatic query naming/custom-name preservation. Reset opens `/?create=1`, the
same clean-query path used by New query; it does not delete previous queries.
Run `python3 -m unittest discover -s worker/tests -v` for version-matched
annotation parsing, optional fields, group ID verification, partial failures,
selected-species profile filtering, alias merging and read-only source protection.

There is no repository-wide automated test runner. The component's
`tests/test_usage.py` is a Selenium/Dash scaffold that expects a text input absent
from the current tree-viewer `usage.py`; it is not established coverage of the
application. PhyD3's `npm test` is a placeholder that intentionally exits with an
error.

Run `node dash_app/phyd3/test-wheel.cjs` for focused wheel-interaction regression
checks: plain scrolling skips layout, wheel bursts share a frame, and pending
modifier-key zoom changes survive subsequent pan events. It also checks repeated
overscrolling, reversing direction, and extreme drag positions against the real
bounded-transform handler. This uses an isolated
handler harness; it does not measure browser rendering or replace visual checks.
Run `node dash_app/phyd3/test-legend.cjs` for the embedded presence legend's
two/four-color mapping, responsive row layout and reserved SVG export space.
The legend is attached outside the panning tree group and replaces the separate
HTML legend for task-linked phylogenetic profiles.

For code changes, use focused syntax/lint checks and the relevant component/image
build. With a configured development stack and reference datasets, manually check
an example CSV request, stage progress, tree/heatmap output, cancellation, and
downloads for affected features. BLAST checks require NCBI access; SSR checks
require a working browser and rendering route. Report missing dependencies or
unperformed runtime checks explicitly. Documentation-only edits do not require
restarting containers or running biological analysis.

### Query history and favicon

The demo menu explicitly loads bundled UniProt, KEGG pathway or InterPro inputs
from `app/demo.py`, with human/Eukaryota compact defaults and BLAST disabled.
`app/species_options.py` promotes available common reference organisms before
alphabetical species; it never adds organisms missing from the selected tree.

`dash_app/app/app/query_history.py` retains the newest 15 saved queries per user;
My queries displays the newest 10. Overflow results and task Redis keys are
removed on query creation or opening My queries. Active overflow jobs are held
in a per-user retirement set until a later cleanup finds them finished. Query
numbers continue increasing. `assets/favicon.ico` is the site-accent Q tab icon.

### Species-profile query strategy

`worker/app/app/tasks/profile_data.py` reads group membership first, filters and
counts distinct genes in Python, then fetches gene names in sorted batches of
500 IDs. It avoids the large membership-to-gene/xref join and resolves overlapping
genes once per batch. `vis_sync.get_corr_data` caches each group's counts and names
in Redis for seven days; keys include the source database path/inode/size/mtime,
selected species and taxid translations, so releases and tree selections do not
share incompatible cached results. UI labels are applied after cache retrieval.
Worker logs report cached/loaded group counts and elapsed load time. The live
reference database remains read-only; no additional live indexes are required.

### Safe database-build progress checks

Read the `.build.json` / `.repair.json` sidecars and container logs. Do not run
long COUNT/join queries on active SQLite build/staging files, even read-only:
DELETE-journal readers can block commits. An external progress count previously
caused a repair timeout. Symbol staging now uses WAL and durable per-batch cursors;
matching progress is in `symbol_stages.matched.sources_checked/total_links`.
Live databases and candidate membership data must stay unchanged during recovery.
