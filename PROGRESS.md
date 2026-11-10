# OrthoQuantum progress report

Recorded 10 November 2026. Paths and commands are relative to
`/home/ilnitsky/best_repository_ever` unless otherwise stated.

## 1. Major interface updates

| Update | Main affected files |
| --- | --- |
| Light-red scientific-tool layout: compact introduction, query settings card, instructions sidebar, narrower dropdowns and protein input | `dash_app/app/app/layout/layout.py`, `dash_app/app/app/assets/typography.css` |
| Consistent locally hosted JetBrainsMono Nerd Font across controls, tables and plots | `dash_app/app/app/assets/typography.css`, `dash_app/app/app/assets/fonts/`, `dash_app/phyd3/js/phyd3.phylogram.js` |
| Q favicon in the existing purple/burgundy accent | `dash_app/app/app/assets/favicon.ico` |
| Working demo button, including fallback when the configured saved demo is missing | `dash_app/app/app/demo.py`, `dash_app/app/app/main.py` |
| Demo menu offers UniProt IDs, KEGG `ko04210` and InterPro `IPR003165`; input help shows multiple identifier examples; available common reference species appear first, followed by alphabetical ordering | `dash_app/app/app/demo.py`, `dash_app/app/app/species_options.py`, `dash_app/app/app/main.py`, `dash_app/app/app/layout/layout.py` |
| Understandable query names, e.g. `'ko04210' #21`, and Reset at the top of query settings | `dash_app/app/app/query_titles.py`, `dash_app/app/app/main.py`, `dash_app/app/app/layout/layout.py` |
| My queries shows the newest 10; retains 15 saved queries and cleans older completed results. Cleanup of active overflow jobs waits until a later history cleanup | `dash_app/app/app/query_history.py`, `dash_app/app/app/main.py` |
| Orthogroup choice table has a 420px scroll area, fixed headers, Select all / Clear all, and selected-row count | `dash_app/app/app/layout/layout.py`, `dash_app/app/app/main.py`, `dash_app/app/app/table_selection.py` |
| More compact results/heatmap presentation; annotation table has compact/detailed statistics, useful column widths, scrolling, CSV export and explicit missing values | `dash_app/app/app/layout/layout.py`, `dash_app/app/app/assets/typography.css`, `dash_app/app/app/main.py` |
| PANTHER entry points are explicit: gene-column label names PANTHER, gene links are underlined, a visible hint explains paralog exploration, and the destination identifies the selected gene/subfamily profile | `dash_app/app/app/layout/layout.py`, `dash_app/app/app/assets/typography.css` |
| BLAST shown as unavailable in a small gray control; Max proteins made smaller and visually secondary | `dash_app/app/app/layout/layout.py`, `dash_app/app/app/assets/typography.css`, `dash_app/app/app/main.py` |
| PhyD3 navigation: bounded scrolling/panning, fewer redraws, highlight and spacing controls, embedded presence legend included in exports | `dash_app/phyd3/js/phyd3.phylogram.js`, `dash_app/phydthree_component/src/lib/components/PhydthreeComponent.react.js`, `dash_app/app/app/layout/layout.py` |

## 2. Backend and querying changes

| Change | Files |
| --- | --- |
| Replaced obsolete Shadowsocks setup with a relay to the host Xray SOCKS proxy | `docker-compose.yml`, `docker-compose.test.yml`, `support_scripts/xray_relay.py` |
| Fixed empty annotations caused by mixing v11 group IDs with unversioned/current metadata requests; pinned metadata and cache namespace to v11, preserved zero/missing values | `worker/app/app/tasks/orthodb_metadata.py`, `worker/app/app/tasks/table_sync.py`, `worker/app/app/tasks/table.py` |
| Replaced the large membership/gene-name join with two passes: deduplicate/filter memberships, then retrieve names in sorted batches of 500 IDs | `worker/app/app/tasks/profile_data.py`, `worker/app/app/tasks/vis_sync.py` |
| Added seven-day Redis profile caching keyed by source database identity, selected species, taxid translations and group; cache hits skip reference SQL reads | Same two files |
| Limited visualization concurrency to one and added actual group progress in batches of five | `worker/app/app/tasks/vis.py` |
| Added streamed v13 download/build tooling and regression checks while preserving the legacy database structure | `support_scripts/orthodb/download_v13.py`, `build_v13.py`, `stream_v13.go`, `test_build_v13.py`, `README.md` |

### Query performance observations

The slow `ko04010` request contained **31 groups across 801 species**. The old
join exceeded a 75-second benchmark cutoff. A full-request run of the replacement
completed in 56 seconds. The subsequent production-path check, after earlier reads
had warmed the database pages, took **19.005 seconds**, followed by **0.088 seconds**
with all 31 profiles cached in Redis. These are profile-loading times, not total
request-to-render times or guaranteed cold-disk performance.

The two production-path passes returned identical counts and names. Counts and
gene-name sets also matched the old SQL for a representative live group. Tests
cover distinct counting, selected species, historical aliases, cache reuse and
invalidation, and keeping the reference database read-only.

## 3. Commented command reference

### Working directory and Docker checks

```bash
cd /home/ilnitsky/best_repository_ever

# Inspect application containers and recent worker progress/errors.
docker-compose ps
docker-compose logs --tail=100 worker
docker-compose logs --tail=100 web

# Rebuild Python/layout/assets changes into the web image and apply them.
# A restart alone does not copy changed source into this image.
docker-compose build web
docker-compose up -d --no-deps web

# Rebuild and apply SQL/profile/metadata worker changes independently.
docker-compose build worker
docker-compose up -d --no-deps worker

# When both services changed, build and recreate both.
docker-compose build worker web
docker-compose up -d --no-deps worker web

# Refresh the proxy relay after changing its configuration or mounted script.
# It forwards 172.17.0.1:10809 to host Xray at 127.0.0.1:10808.
docker-compose up -d --no-deps --force-recreate xray-relay
```

These application service updates do not restart the separate
`orthodb-v13-build` container or switch database releases.

### Tests used

```bash
# Demo fallback, titles, table selection and saved-query cleanup.
python3 -m unittest discover -s dash_app/app/tests -v

# OrthoDB metadata parsing and profile querying/caching regressions.
python3 -m unittest discover -s worker/tests -v

# Focused PhyD3 scrolling/bounds and embedded-legend/export checks.
node dash_app/phyd3/test-wheel.cjs
node dash_app/phyd3/test-legend.cjs

# Streamed importer fixture tests, including compatible schema and recovery.
# Requires the compiled Go streamer below.
python3 support_scripts/orthodb/test_build_v13.py

# Python syntax and whitespace checks used alongside the focused tests.
python3 -m py_compile worker/app/app/tasks/profile_data.py worker/app/app/tasks/vis_sync.py
git diff --check
```

Additional session-specific smoke tests were run from `/tmp`. They are diagnostic
artifacts, not committed project test entry points:

```bash
# Local read-only comparison of old/new SQL for the saved 31-group request.
# Requires /tmp/query-rows.json captured from that particular saved query.
python3 -u /tmp/benchmark-profiles.py

# Compare a representative live group's counts/names and a cached repeat.
python3 -u /tmp/profile-validation.py

# Full production-path test: first database load, then Redis-cache repeat.
# Reads the saved request and source DB; writes normal expiring profile-cache keys.
docker-compose run --rm --no-deps --user www --entrypoint python3 \
  -v /tmp/profile-production-smoke.py:/tmp/profile-production-smoke.py:ro \
  worker /tmp/profile-production-smoke.py

# Verify retained history using temporary Redis records, cleaned after the check.
docker-compose run --rm --no-deps --user www --entrypoint python3 \
  -v /tmp/ortho-history-smoke.py:/tmp/ortho-history-smoke.py:ro \
  web /tmp/ortho-history-smoke.py
```

### Downloading v13 archives

```bash
# Download only the seven reference tables needed for this migration, plus README.
# Resume partial downloads and verify official MD5 hashes. No gunzip step is needed.
python3 support_scripts/orthodb/download_v13.py \
  --destination /home/ilnitsky/OrthoDB_loads_v13 \
  --proxy socks5h://127.0.0.1:10808 --jobs 2

# Review verified download status and available disk space.
cat /home/ilnitsky/OrthoDB_loads_v13/download-status.json
df -h /home/ilnitsky/PANTHERDB
```

### Database creation

The fresh-build command is recorded for reproducibility. **Do not launch another
builder while `orthodb-v13-build` is running.** The builder refuses existing
output/staging files; do not delete those files to force a second run.

```bash
# Compile the Go gzip-to-TSV streaming helper, without uncompressed staging files.
mkdir -p support_scripts/orthodb/bin
go build -o support_scripts/orthodb/bin/stream_v13 \
  support_scripts/orthodb/stream_v13.go

# Equivalent Docker compilation when Go is not installed on the host.
# This session used the cached golang:1.18.0-bullseye image for compilation.
docker run --rm --user "$(id -u):$(id -g)" \
  -e GOCACHE=/tmp/go-cache -e GO111MODULE=off \
  -v /home/ilnitsky/best_repository_ever:/src -w /src \
  golang:1.18.0-bullseye \
  go build -o support_scripts/orthodb/bin/stream_v13 \
  support_scripts/orthodb/stream_v13.go

# Fresh build: clone the live DB's schema into a separate v13 candidate.
# The source is read-only; the app continues using orthodb.db.
python3 -u support_scripts/orthodb/build_v13.py \
  --source /home/ilnitsky/PANTHERDB/orthodb.db \
  --archives /home/ilnitsky/OrthoDB_loads_v13 \
  --output /home/ilnitsky/PANTHERDB/orthodb_v13.db \
  --streamer support_scripts/orthodb/bin/stream_v13
```

The active build was recovered after a parser incompatibility with v13 mapped-only
`u_...` identifiers and an interrupted read-only recovery validation. The following
is the **historical detached recovery launch**, not a normal restart command:

```bash
# The --resume-validation flag is specific to that validated recovery state.
# --resume-genes is also narrowly guarded, not a generic crash-resume option.
docker run -d --name orthodb-v13-build \
  --user "$(id -u):$(id -g)" --memory 1g --cpus 1.5 \
  --entrypoint python3 \
  -v /home/ilnitsky/best_repository_ever/support_scripts/orthodb:/builder:ro \
  -v /home/ilnitsky/OrthoDB_loads_v13:/home/ilnitsky/OrthoDB_loads_v13:ro \
  -v /home/ilnitsky/PANTHERDB:/home/ilnitsky/PANTHERDB \
  -v /home/ilnitsky/PANTHERDB/orthodb.db:/home/ilnitsky/PANTHERDB/orthodb.db:ro \
  best_repository_ever_worker -u /builder/build_v13.py \
  --source /home/ilnitsky/PANTHERDB/orthodb.db \
  --archives /home/ilnitsky/OrthoDB_loads_v13 \
  --output /home/ilnitsky/PANTHERDB/orthodb_v13.db \
  --streamer /builder/bin/stream_v13 --resume-validation
```

### Monitoring the existing database build

```bash
# Progress report: completed stages, imported rows, checks and compatibility notes.
cat /home/ilnitsky/PANTHERDB/orthodb_v13.db.build.json

# Current progress messages and whether the process is still running.
docker logs --tail=20 orthodb-v13-build
docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' orthodb-v13-build

# Resource usage and remaining storage.
docker stats --no-stream orthodb-v13-build
df -h /home/ilnitsky/PANTHERDB
```

## 4. Last verified build snapshot and remaining work

At the last check reported in this session:

- Genes complete: **74,824,521 rows**; 164,066,413 source records examined.
- Membership import: approximately **270 million rows**, **60.8% of the archive
  consumed**, approximately 77,000 imported rows/second.
- Candidate database approximately **8 GiB** at that point; **90 GB** free on `/home`.
- The builder was running normally. These figures are a snapshot, not live status.
- Index construction, ANALYZE and validation still follow membership ingestion.
  Archive percentage is not an overall build percentage.

The candidate preserves the live three-table/six-explicit-index structure and
legacy packed gene-ID format. Mapped-only `u_...` IDs cannot fit that format and
are excluded; 26 such mapped gene records were reported. Historical configured
levels missing in v13 are retained as compatibility definitions and listed in the
report. See `support_scripts/orthodb/README.md` for the exact policies.

The final candidate filename is published only after schema comparison, SQLite
`quick_check`, row-count checks and representative lookups. This is not a full
`integrity_check`. **The application still uses v11.** Moving it to v13 requires
validating the completed candidate and aligning the local DB, online search and
metadata endpoints, generated links and release-specific caches together.

## 5. Separate JavaScript/Canvas experiment

`experiments/orthoquantum-lite/` is an independent, runnable test website. It has
a plain-JavaScript frontend, Canvas profile viewer, browser-worker correlations,
Node HTTP API and a small read-only Python/SQLite adapter. No npm runtime
dependencies, Dash, React, PhyD3 or production Redis queues are involved.

It includes real UniProt/KEGG/InterPro demos, fresh reference-organism-scoped
lookups, group selection, PANTHER subfamilies, file import/export, local browser
history and synthetic stress datasets. It runs under the separate
`orthoquantum_lite` Compose project on `127.0.0.1:8051`; production uses 8050.

See its README for startup/SSH commands, source files and limits. Its
VALIDATION.md records browser, API and read-only-database checks, including
20,000 × 200 synthetic navigation. It is a reviewable prototype rather than a
production migration; branch-length rendering, BLAST and full scientific parity
remain outside this experiment.

## 6. V13 mapping repair after final validation failed

The membership import completed at **443,783,953 rows**, all six indexes finished,
and the initial candidate reached approximately **35 GiB**. Publication stopped
at the human AGO1 lookup. Auditing showed that the imported human summary rows
had no gene names and lacked familiar canonical UniProt accessions; the official
v13 API independently identified `8905661at2759` for Q9UL18.

Added the Go streamer's `xrefs` mode and
`support_scripts/orthodb/repair_v13_mappings.py`. The repair stages dedicated
UniProt/NCBIgenename aliases separately, preserves existing mappings/fallback
names where appropriate, and replaces only the candidate's genes/indexes in one
transaction. Memberships and their indexes are retained. The detached repair job
is `orthodb-v13-mapping-repair`; live v11 remains unchanged.

Four importer/repair fixture tests passed, including unchanged live-file bytes,
schema and membership checks, alias deduplication, name-only genes, and rollback
after an injected error. See the orthodb README for commands and the live
`orthodb_v13.db.repair.json` sidecar for actual progress; starting the repair is
not a claim that the candidate is already repaired or published.

The first repair recovered canonical UniProt aliases, but validation stopped:
the actual v13 cross-reference archive has no `NCBIgenename` records. The staged
aliases remain available for the next repair; neither candidate genes nor live
data were replaced. Gene-symbol recovery still needs an authoritative mapping.

## 7. PANTHER v19 candidate and direct ortholog views

Added `support_scripts/panther/{build_v19.py,relations.go,tree_assets.py,test_v19.py}`
and README with source URLs, commented build/monitor commands and migration
requirements. The detached `panther-v19-build` job downloaded all 149 source files.
Classification validation passed: 2,017,190 rows across 144 species, including
the four human UniProt demo identifiers. Relationship import is running; this
is not a completed or published database yet.

The bundle preserves the legacy classification schema and adds a separately
indexed ortholog/paralog database plus matching tree/map. It retains LDO, O and
P types separately; shared family membership does not imply direct orthology.
Production databases and containers remain unchanged.

The separate lightweight site's `bridge.py`, `server.mjs`, `compose.yml` and
frontend now support a validated v19 bundle and subfamily/LDO/LDO+O selection.
Until publication the site keeps its existing reference and disables v19 modes.
Publication is detected after refresh, with release-aware cache invalidation.

Validation: three PANTHER pipeline fixtures and five prototype adapter fixtures
passed, including reverse ortholog lookup, exclusion of paralogs, duplicate
target handling, matching tree IDs and unchanged source files. The rebuilt test
site passed its browser smoke run with no errors or failures.

## 8. Lightweight viewer overview and image export

Port 8051 now defaults to clustered columns and gene copy counts (including
count-based Pearson; clustering retains binary-distance semantics). Added column
spacing controls and Fit whole plot, which fits both axes and hides unreadable
names. Subpixel overview cells aggregate findings rather than allowing absent
neighbors to erase them. Reset restores readable spacing.

`public/whole-image.mjs` exports the complete current species-filtered profile as
SVG, retaining column order, tree, full names, status legend and copy counts at
readable spacing. The existing visible PNG remains available. SVG avoids raster
canvas size limits; very large files may still challenge external viewers.
Affected files: `public/{app.mjs,index.html,viewer.mjs,whole-image.mjs}`, README,
VALIDATION, and model/browser export checks. Only the `orthoquantum_lite` service
was rebuilt; production and database jobs were left alone.

Verification: eight Node checks passed. Browser checks passed for defaults,
column spacing, full SVG download/XML validity, full-view bounds at 165 and
20,000 species, reset, existing workflows and mobile overflow. No browser runtime
errors or failed requests were recorded.

## 9. Linked orthogroup and PANTHER views on port 8051

Added Orthogroups / PANTHER buttons above annotations. A gene drill-down keeps
the orthogroup dataset and latest PANTHER dataset in separate in-memory slots.
Switching restores each view's species/annotation filters, order/count mode,
spacing, fit mode, selected column, plot/table position and cached correlations.
No database query is needed to switch. New query results, demos, file/history
loads start a new pair; Reset clears the pair. Individual saved datasets remain
in browser history. The linked pair itself is page-session state.

Affected files: `experiments/orthoquantum-lite/public/{app.mjs,index.html,style.css}`,
README and `tests/browser.smoke.mjs`. Rebuilt only the separate 8051 test service;
production and database jobs were left unchanged.

Browser verification passed for a real NPM1 drill-down and both switch directions,
including exact retained orthogroup filters/order/spacing/scroll and independent
PANTHER settings. Existing workflows and mobile checks passed with no errors.

## 10. Authoritative OrthoDB v13 gene-symbol recovery

Added `support_scripts/orthodb/complete_v13_symbols.py` and fixture tests; extended
Go streaming with `geneids` mode. The completed alias staging is reused while
NCBI GeneIDs are joined to current NCBI gene_info primary/authority symbols with
exact taxid agreement. No descriptions or cross-release packed gene IDs are used
as symbol evidence. Provenance and unmatched/mismatched counts are recorded.

Prepared genes use a separate symbols SQLite file; original reusable aliases
and membership indexes are retained. Existing transactional apply/validation is
reused. `repair_v13_mappings.py --resume-staged` also accepts the recorded symbols
file after a ready checkpoint. Six tests passed, including unchanged live bytes,
schema/membership checks, taxonomy rejection and rollback. A detached
`orthodb-v13-symbol-repair` job was started; completion still requires actual
full-data validation. See the orthodb README for commented commands.

## 11. Branch snapshot and lightweight app promotion

Created `snapshot/dash-and-lite` to preserve the complete current
source state, then derived active branch `main/lightweight` directly from it.
Secrets, local databases/input tables, screenshots and review PDFs were excluded.

On the derived branch, promoted `experiments/orthoquantum-lite/` to `web/` and
made it the root Compose default. Added `compose.sh` to retain the existing
`orthoquantum_lite` project/port 8051 and updated `rebuild.sh` to use it without an
automatic Git pull. Preserved Dash configs as `docker-compose.legacy.yml` and
`docker-compose.legacy-test.yml`, with explicit `rebuild-legacy.sh`. The default
test override now binds main web source. Existing Dash on 8050 was not cut over.

The main stack now supplies its own Xray relay on Docker gateway port 10810;
legacy remains on 10809. Both forward to host Xray 10808. The relay helper accepts
an optional port setting while keeping the old default. Updated app branding,
health metadata, moved tree-export paths, root README and current branch guide.
Database IDs/releases, detached database jobs, Redis and legacy result volumes
were not migrated or removed.

Validation: eight Node and five Python checks passed from the new `web/` path;
Compose configuration and shell/Python/JS syntax checks passed. Main image was
rebuilt through the new root wrapper. Live proxy-free checks cover health,
frontend modules/demos and read-only configuration; the independent relay reached
OrthoDB with HTTP 200. Browser tooling was no longer present in /tmp, so the full
browser suite was not repeated during promotion; its earlier report is retained.


## 12. Main/legacy frontend port swap

The lightweight main application now binds host loopback 8050 (container 8051).
Legacy Dash moves to host loopback 8051 (container 8050). Existing site proxies
targeting 8050 therefore reach the main application. Root and compatibility
Compose mappings/documentation were updated; the legacy host port is overridable
through LEGACY_ORTHOQUANTUM_PORT. No database/worker/Redis volumes are changed.

The main server accepts configured PUBLIC_ORIGINS, defaulting in Compose to HTTP
and HTTPS orthoq.bioinf.fbb.msu.ru. This handles both preserved and loopback-rewritten
Host headers behind a proxy while rejecting unrelated hosts/origins. Focused HTTP
checks cover both schemes and proxy behavior.

Port swap completed and verified: main /api/health on 8050, legacy Dash HTML on
8051, and the main site's HTTPS Origin all returned HTTP 200. Nine Node checks
passed. Only frontend services were stopped/recreated; background jobs were not
restarted. Main smoke-test defaults now use 8050.

## 13. Restore descriptive copy and remove public stress tests

Restored the previous "Explore phylogenetic profiles" heading and biological
introductory/About copy in the lightweight main site. Removed the public stress
controls and synthetic-data generator, plus its obsolete browser UI steps.
Historical benchmark results remain documented. No BLAST availability claim was
restored while BLAST is disabled. Changed `web/public/{index.html,app.mjs}`,
browser smoke steps and web README; JS syntax and diff checks passed. Deploys
only the main frontend, leaving legacy and database jobs alone.
