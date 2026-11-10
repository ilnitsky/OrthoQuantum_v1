# Promotion note

On `main/lightweight`, the previously isolated implementation is now `web/` and
the root Compose default. Earlier measurements below describe the same viewer
before promotion. The legacy Dash service remains on 8050.

# Validation record — 10 November 2026

The experiment is isolated in `web`, with its own
`orthoquantum_lite_lite_1` container and loopback port 8051. Production services,
Redis queues and database contents were not migrated or rewritten.

## Checks completed

- **7 Node checks**: real bundled datasets/tree alignment; malformed-data rejection;
  tree filtering; bounded viewport ranges after overscroll; binary/count Pearson
  behavior and constant-profile handling; CSV roundtrip; static HTTP and async API
  request validation/configuration/result reuse.
- **4 Python checks**: selected-species resolution and distinct counts; historical
  taxonomy alias merging; read-only enforcement/source bytes unchanged; invalid
  input rejection; PANTHER support thresholds/ambiguous family selection; online
  resolution scoped to the selected organism rather than its entire clade.
- **Real Chromium browser suite** against the running container: all three demos;
  scroll-end/reverse behavior; species search; count mode; clustering; JSON
  download/import; annotated phyloXML category preservation; unsafe XML rejection;
  real local UniProt resolution/group selection/profile building; real PANTHER
  gene-button navigation and SESN2 data; synthetic 20,000 × 200 navigation; mobile
  layout at 390 × 844 without page-wide overflow. No browser runtime errors or
  failed HTTP responses were recorded in the completed run.
- Optional fresh KEGG/InterPro checks are in `tests/live_api_smoke.py`; their latest
  outputs are written to `artifacts/online-api-results.json`. These require a
  working upstream API/proxy; they are separate from offline fixture tests.

Final live-search check after reference-organism scoping: `IPR003165` returned
11 matches and built two profiles across 165 species in 2.188 seconds;
`ko04210` returned a capped 100 of 5,080 candidate hits and built two profiles
in 6.037 seconds. The latter explicitly reported truncation. This validates the
API/selection/profile pipeline, **not biological KEGG pathway membership**; the
underlying search is broad and remains a review item before scientific deployment.

The initial browser pass exposed an unindexed PANTHER `Gene OR Uniprot` condition
that scanned the 2.26 GiB table. It was replaced by indexed Gene lookups; UniProt
inputs resolve symbols through the indexed OrthoDB mapping first. Fresh online
validation also exposed overly broad clade-wide matches; resolution now uses the
selected reference taxid while membership profiles still cover the selected tree.

## Recorded browser measurements

Completed run: **2026-11-10 08:47:20 UTC**, Chromium **141.0.7390.37**,
1440 × 1050 viewport, device pixel ratio 1. Measurements came from the final
container browser pass before the later reference-organism search-only correction.
The viewer code was unchanged by that correction.

| Dataset | Navigation samples | Draw work median | Draw work p95 | Maximum | Visible / total rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| Real KEGG snapshot: 807 rows × 31 groups | 60 | 3.3 ms | 4.2 ms | 7.5 ms | 31 / 807 |
| Synthetic: 20,000 rows × 200 groups (4 million cells) | 60 | 3.2 ms | 4.0 ms | 4.6 ms | 30 / 20,000 |

Both used **two Canvas elements total**, with no per-cell SVG/DOM objects.
The synthetic correlation worker was allowed to run while navigation was tested;
its large-result completion time is not claimed by this navigation check.

These are timed **draw operations**, not end-to-end FPS, cold-disk query latency,
or a controlled speedup comparison against production Dash. They exclude initial
file parsing, layout preparation, correlation calculations and browser compositor
costs. Native scrolling remains bounded; the displayed rows are culled to the
viewport rather than rendering the entire matrix on every move.

A two-group local profile count read reported 0.038 seconds with warm filesystem
pages in the browser run. It is not comparable to the earlier production
31-group/full-annotation benchmark and is not a cold-read guarantee.

The prototype container was observed at **52.84 MiB memory** after browser checks,
with a configured 384 MiB cap. This is a snapshot, not a measured peak.
Frontend JavaScript plus CSS totals approximately **52 KiB uncompressed / 16 KiB
when gzip-compressed as a combined size estimate**; this excludes fonts and real
reference examples. The server currently serves the individual source modules
without a bundling/compression step.

## Review artifacts

Locally generated files, intentionally excluded from Git/image context:

- `artifacts/desktop.png`
- `artifacts/mobile.png`
- `artifacts/panther.png`
- `artifacts/stress.png`
- `artifacts/browser-results.json`
- `artifacts/online-api-results.json`

Browser tooling was installed under `/tmp/ortho-lite-browser`. Missing GBM/Wayland
libraries were extracted into that directory for test use; host packages were not
installed. No browser tooling is required to run the website itself.

See README.md for deliberate scientific/feature boundaries: topology-only branches,
first-160-group correlations, copy-count/binary mode differences, legacy unknown
IDs, v11-specific seed mappings, local PANTHER provenance, CSV without topology,
no BLAST submission, viewport-only PNG and complete SVG export.

## Whole-plot controls (2026-11-10)

The updated browser run passed with no runtime errors or failed HTTP requests.
It checks clustered/count defaults, column spacing, fitting all 165 demo rows
inside the viewport, valid downloadable full SVG with offscreen species names,
reset, and fitting the 20,000 × 200 stress dataset on both axes. Dense overview
aggregation is a one-off full-data draw, not the bounded navigation benchmark;
its pixels summarize statuses and should not be used to read exact copy counts.
`artifacts/overview.png` records that view. Mobile overflow checks still pass.
Eight Node checks pass, including filtered/reordered/escaped SVG output, plus the
existing API/model cases. Current draw timings are in browser-results.json.

## Linked PANTHER navigation (2026-11-10)

Browser round-trip checks passed: a real NPM1 PANTHER drill-down retains the
orthogroup dataset, and the buttons restore its exact species filter, annotation
filter, column order, row/column spacing and scroll position. Switching back to
PANTHER retains its separate species filter and spacing. Existing export,
overview, data-loading and mobile checks also passed with no runtime errors or
failed requests. The latest report is `artifacts/browser-results.json`.

## Main-application promotion

After relocation to `web/`, eight Node and five Python checks passed. Root Compose
and shell syntax validated; the main image was rebuilt on its existing 8051 port.
Live health/static/configuration checks and the independent 10810 Xray relay
were checked separately. The full browser suite was not repeated for this
promotion because its temporary tooling was unavailable; earlier browser reports
above apply to the same viewer behavior before relocation.

## Main/legacy port swap

Lightweight main now maps loopback 8050 to its internal 8051; legacy Dash maps
loopback 8051 to internal 8050. Nine Node checks passed, including configured
HTTP/HTTPS origins, proxy-rewritten Host handling and rejection of unrelated
hosts/origins. Live main health, legacy Dash HTML and the public Host/HTTPS Origin
probe each returned HTTP 200 after the swap. Only the two frontend containers
were recreated; workers, Redis, database builders and reference mounts were not
changed. Smoke-test defaults now target main port 8050.
