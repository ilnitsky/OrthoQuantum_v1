# OrthoQuantum web application

This is the main JavaScript/Canvas implementation on `main/lightweight`, promoted
from the isolated 8051 experiment. Default deployment and branch/legacy details
are in the [root README](../README.md). Reference databases remain read-only.

```bash
# From the repository root:
./compose.sh up -d --build
./compose.sh logs --tail=50 lite
# Or directly, without a frontend build/npm installation:
ORTHODB_PROXY=socks5h://127.0.0.1:10808 PORT=8050 node web/server.mjs
```

Open http://127.0.0.1:8050 on the server, or forward it:

```bash
ssh -N -L 8050:127.0.0.1:8050 ilnitsky@calculator
```

The old standalone `web/compose.yml` remains a compatibility configuration using
relay port 10809; new deployments should use the root configuration and wrapper,
which provide an independent relay on 10810. Both use the same app/project/main
port and must not be started as competing deployments. The Dockerfile still uses
the tested legacy cached runtimes; see the root README's runtime limitation.

## What is implemented

- Plain JavaScript frontend and Node HTTP server, with **zero npm runtime dependencies**.
- Locally hosted JetBrainsMono Nerd Font and the existing red/purple palette.
- Real query flow: choose tree/reference species, resolve gene names, UniProt,
  group IDs or online KEGG/InterPro inputs, select matching groups, build profiles.
  Online resolution uses the selected reference organism, not all organisms in
  the clade. Presence profiles still span the selected species tree.
- Real read-only SQLite membership queries, grouped into a distinct-gene count
  matrix. Background jobs expose progress and cancellation. Only one adapter job
  runs at a time to avoid multiplying disk contention.
- Three bundled real-data demos, usable even without reference databases/network.
- **Canvas tree + grid**: native bounded scrollbars, drag-to-pan, row spacing,
  column spacing, fit-whole overview, horizontal navigation, short headers, hover details, click details,
  species search, input/coverage/cluster ordering, binary/count views.
- Visible-row/column rendering. Invisible subtrees are pruned during branch drawing.
  One Canvas represents the profile; there is no DOM element per branch or cell.
- A browser worker computes Pearson correlations and average-linkage ordering.
  Constant profiles yield undefined/gray cells, not invented numeric correlations.
- PANTHER drill-down uses the local database and species mapping. Multiple matching
  families require a choice. Subfamilies require at least nine records, matching
  the existing application's threshold. A previous dataset remains in local history.
- Annotated phyloXML import, full dataset JSON import/export, count-matrix CSV
  import/export, correlation CSV, a PNG of the **visible viewport**, and a complete
  SVG image with readable names/counts and the current species filter/column order.
- Fifteen datasets retained in browser IndexedDB; newest ten shown. Imported files
  are parsed locally and are not uploaded to the server.

## Important scientific/feature boundaries

This implementation does not yet have complete scientific parity with legacy Dash.

- Branches show **topology only**, not branch-length-scaled evolutionary distances.
- Cluster ordering and **Gene copy counts** are the defaults. The selected view
  also controls Pearson correlation (raw counts or binary presence). Clustering
  continues to use binary-profile distances. Species search filters the viewport
  and whole SVG image; dataset JSON/CSV and correlations retain all species.
- Fit whole plot compresses both axes and automatically hides species labels below
  12 pixels per row and column labels below 8 pixels per column. Subpixel cells
  aggregate status with findings taking priority. Hover shows the cell under the
  pointer; use normal spacing or SVG for exact inspection. Whole SVG uses readable
  spacing and avoids raster canvas dimension limits; exceptionally large vector
  files can still be demanding for external image viewers.
- Correlations/clustering are limited to the first **160 groups**, with an explicit
  status note for larger matrices. The tree/grid still displays all loaded groups.
  The correlation plot does not reproduce Seaborn's dendrogram presentation.
- Fresh lookups build up to 200 profiles; candidate selection is capped at 100
  matches. Broad searches report truncation instead of claiming complete results.
  KEGG strings are delegated to OrthoDB's search endpoint, not resolved through
  an independently verified KEGG pathway-membership service. In the live check,
  `ko04210` produced thousands of candidate hits; reviewing matches or using
  specific protein identifiers is necessary. The bundled KEGG snapshot reproduces
  an existing application's saved selection, not a newly validated pathway list.
- Group annotations are lightweight. Fresh local identifier matches contain
  reference-organism gene names; full remote evolutionary statistics are not fetched.
- Per-cell full gene-name lists are deliberately omitted from fresh queries. The
  viewer shows copy counts/status and group details, avoiding a large annotation
  join on every species profile. This changes the tooltip contents from PhyD3.
- PhyloXML preserves legacy two/four-color presence states. Its original copy
  counts cannot be recovered when the XML stored only binary/category values.
- CSV has no tree topology: imported CSVs explicitly show a flat species list.
- BLAST submission, production task/session migration and server-rendered full-tree
  publication is not implemented (whole-image SVG export runs in the browser). The prototype does not read production
  users' sessions or Redis history.
- Local reference DB release is configured, not inferred automatically. **Do not
  point v11 group seeds/endpoints at a v13 database.** Align them together first.

## Real example provenance

`public/data/demo-seeds.json` records the source group IDs. `build_demos.py`
regenerates count matrices through `bridge.py`, opening the reference DB read-only.

| Demo | Data |
| --- | --- |
| UniProt | Q9UL18, P06748, Q92484, P05026; four groups, 165 compact-Eukaryota species |
| KEGG | ko04010; 31 groups from a query resolved by the existing app during this session; 807 leaves from its Metazoa template |
| InterPro | IPR003165; **first five of eleven** v11 API matches; 165 species; explicitly a subset |

Some legacy tree leaves have nonnumeric/unknown taxonomy IDs. They are retained in
view order, with zero findings where no local mapping exists. Thus the Metazoa
snapshot has 807 total tree rows rather than the 801 numeric taxa used in the
production SQL timing check. This is recorded in the dataset source notes.
PANTHER's local release provenance is unspecified and is labeled accordingly.
The synthetic stress matrices are deterministic random data, never biological evidence.

```bash
# Rebuild the v11-compatible bundled snapshots only when deliberately refreshing them.
python3 web/build_demos.py
```

## Files

| File | Responsibility |
| --- | --- |
| `server.mjs` | Static HTTP serving, bounded job queue, progress/cancellation, in-memory result reuse |
| `bridge.py` | Python standard-library SQLite adapter, optional curl search, PANTHER extraction; no Dash/Redis imports |
| `public/app.mjs` | Forms, selection, local history, imports/exports and dataset switching |
| `public/viewer.mjs` | Canvas drawing, viewport culling, scroll/drag/zoom and hit testing |
| `public/model.mjs` | Validation, topology layout, Pearson/clustering, CSV handling |
| `public/compute-worker.mjs` | Browser-worker entry point for correlation/clustering |
| `public/import-xml.mjs` | Annotated phyloXML compatibility reader |
| `public/data/` | Real tree templates, source seeds, bundled reference examples |
| `export_trees.py`, `build_demos.py` | Reproduce the bundled tree templates and real-data examples |
| `tests/` | Model, HTTP, SQLite safety/correctness and browser smoke/stress tests |
| `artifacts/` | Local browser screenshots and measured results; excluded from Git/image context |
| `compose.yml`, `Dockerfile` | Separate loopback-only test deployment |

Fonts retain their original license files in `public/fonts/`.

## Validation

```bash
# Node 18+; HTTP tests bind an ephemeral loopback port.
node --test web/tests/*.test.mjs

# Standard-library Python fixtures; verify writes are rejected and source bytes unchanged.
python3 -m unittest discover -s web/tests -p 'test_*.py' -v

# Optional external API smoke: fresh InterPro and KEGG searches plus profile reads.
# Requires the running test server, local reference DB and a working proxy/network.
python3 web/tests/live_api_smoke.py

# Optional browser test. Playwright is test tooling, not a runtime dependency.
# Install it in a temporary directory if desired:
npm install --prefix /tmp/ortho-lite-browser playwright@1.56.1
node /tmp/ortho-lite-browser/node_modules/playwright/cli.js install chromium --only-shell

# Start the prototype before running this. Supply browser libraries through
# LD_LIBRARY_PATH if your host lacks them; no host package installation is required.
PLAYWRIGHT_MODULE=/tmp/ortho-lite-browser/node_modules/playwright/index.mjs \
  node web/tests/browser.smoke.mjs
```

The browser test covers demo loading, scroll bounds/reversal, search, counts,
clustering, export/import roundtrip, real UniProt lookup, real SESN2 PANTHER data,
real-data navigation and mobile overflow. Measurements are saved to
`artifacts/browser-results.json`, with desktop/mobile/PANTHER/stress screenshots.
They measure draw work on this machine, not a guarantee of end-to-end FPS on
other hardware. See `VALIDATION.md` for the final recorded run and limitations.

## Linked orthogroup / PANTHER views

Clicking a gene keeps the current orthogroup dataset in memory and opens PANTHER
alongside it. Use the **Orthogroups** / **PANTHER** buttons above the annotation
table to switch without repeating database queries. Each view retains species
and annotation filters, count/order mode, row/column spacing, whole-plot mode,
scroll position and completed correlations. The PANTHER button names the latest
opened profile. Another PANTHER gene replaces that PANTHER slot while keeping the
orthogroup view. A new query result, demo, imported file or history selection
starts a new pair; Reset clears it. This linked pair lasts for the page session;
saved datasets remain individually available through Recent datasets.

The public stress-test controls and synthetic-data generator have been removed.
Historical stress measurements remain in VALIDATION.md; the browser smoke suite
now exercises real demos and main application flows.
