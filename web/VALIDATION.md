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

## Zoomable correlation clustermap

Twelve Node checks passed, including reordered hit-testing under anchored zoom,
extreme pan/zoom bounds, and dendrogram leaves matching the shared axis order.
The 160-column browser fixture passed after the real reference configuration
loaded: clustered axes, no nested scrollbars, +/−/wheel zoom, full-name tooltip,
bounded drag, Fit, query-order switching and mobile layout. No runtime errors.
Screenshots/report: `artifacts/clustermap-{fit,zoom,mobile}.png` and
`artifacts/clustermap-results.json`. Synthetic data exists only inside this test;
no public stress-test controls were restored. Browser libraries/tooling are under
/tmp, with no host package installation or runtime dependency added.

## Coefficient annotations at readable zoom

Browser checks passed for automatic two-decimal cell labels after zoom, no labels
in the dense fitted matrix, values drawn from the correlation matrix, and hiding
again after Fit. Explicit bright/dark/undefined-cell fixtures verify black/white
contrast and the undefined em dash. Existing zoom, pan, hover, axis ordering and
mobile checks also passed with no runtime errors. A focused screenshot is saved
locally at `artifacts/clustermap-coefficients.png` (not committed).

## Binary correlations and correlation-distance hierarchy

Twelve Node checks passed after making Pearson strictly binary (count > 0).
Changing nonzero copy magnitudes does not change the matrix; the hierarchy uses
1 − r and excludes constant profiles from its tree, appending them last. Tests
cover mixed/all-constant datasets without inventing numeric correlations.
The live browser fixture confirmed that switching the profile display between
presence and copy counts leaves its correlation matrix unchanged. Existing
clustering, zoom/pan, coefficient, contrast and mobile checks passed with no
runtime errors. Screenshots show the new zero-centered blue/white/red palette.

## Restored My queries and full legacy guide

Fourteen Node checks passed, including queue positions, cancelled-job removal
from positions, independent active requests, summary responses without result
payloads, `/about` and all ten PNG image routes. All copied tutorial images match
the legacy originals byte-for-byte.

A Chromium test used a real Q9UL18 lookup to verify job tracking, New query without
cancelling earlier work, reopening matches, building a profile, and reopening its
local saved result without another query. Help/About opened separately without
losing the main plot; all ten images decoded successfully. Mobile header/menu
layout had no page overflow. No browser runtime errors. Artifacts are
`my-queries.png`, `my-queries-mobile.png`, `about-guide.png` and
`jobs-about-results.json`. Run with the existing temporary Playwright setup:
`node web/tests/jobs-about.browser.mjs`.

## Named PANTHER family columns

Six Python adapter fixtures passed, including rare names, same-name/different-SF
merging, duplicate accession protection, unassigned names, reference-genome
scoping, indexed v19 accession lookup without older OrthoDB mappings, and source
read-only protection. A direct read of published v19 PTHR22747 confirmed all five
named groups and their protein/species counts listed in README.md.

The real NPM1 browser flow passed: direct orthologs remain one query-protein
column; Compare opens the five-name family profile; the seven-protein CORE
DOMAIN-CONTAINING group is present; NUCLEOPHOSMIN combines six SF IDs. Changing
PANTHER mode reloads the same query, and original orthogroup view switching and
mobile layout remain valid. No browser errors. Artifacts:
`npm1-named-subfamilies.png` and `panther-subfamilies-results.json`.

### Full-dataset clustering

`node --test tests/*.test.mjs` includes full 1,000-group coverage and compares
nearest-neighbor-chain average linkage with an exhaustive implementation.
`tests/full-cluster.browser.mjs` checks all columns enter both plot orders,
including an identical profile at column 999, and measures cached redraws.
The deployed Chromium run clustered 1,000 groups × 165 species in ~1.6 seconds
and averaged ~4.6 ms per clustermap redraw. The first-160-group cap is removed.

### v13 main deployment and 2,500 cap

Main HTTP checks passed for v13 configuration, AGO1/NPM1 symbol resolution,
profile creation and rejection of v11 matches. Nine original adapter checks plus
the larger 2,500-group stdin regression passed (10 total); 17 Node tests passed.
`TEST_GROUPS=2500 ... node tests/full-cluster.browser.mjs` included every group
in both plot orders, clustering in ~1.8 seconds and redrawing in ~8.9 ms. The
Max findings browser check accepted 2,500 and rejected 2,501; default/reset=100.

### Expanded v13 species and levels

18 Node tests and 13 adapter/catalog/supplement tests passed; the latter were
also run inside the actual deployed Python 3.9.5 / SQLite image. The complete
supplement passed quick_check and contains 4,977,455 memberships for nine levels.
The v13 catalog test checks all 160 level trees for unique species, complete
rows/tree alignment and selected genomes. A representative fixture verifies that
renamed canonical taxonomy IDs resolve correctly and alternate assemblies do not
inflate counts. Supplement fixtures verify read-only access and base-identity
guards, as well as isolated publication from a tiny verified gzip input.

`tests/v13-species.browser.mjs` passed against the main deployment: 162 choices,
5,486 / 2,320 / 2,416 / 410 / 93 species in extended Eukaryota, Metazoa, Fungi,
Viridiplantae and Lophotrochozoa. A real NPM1 profile loaded all 5,486 rows, 2,023
with findings, and one gene in the selected human genome. Common options and
mobile overflow checks passed. Actual read-only queries built positive profiles
for Fungi, plants, Lophotrochozoa, SAR, Discoba, Metamonada, Haptista and
Cryptophyceae. Taxonomy trees retain unresolved polytomies and infer no distances.

### GO resolution timeout

The query budget fixture simulates a long interval between SQL statements and
checks that the next statement still succeeds, while an actually slow statement
is interrupted. Annotation coverage verifies GO skips gene-name resolution,
loads reference names once and uses the group index without changing aliases or
source files. Pagination covers 1,000 + 1,000 + 500 records and repeated-page
protection. The live full-limit GO:0005730 adapter check returned 2,500 results
in ~97 seconds; the upstream reported 5,083 total matches. See
`tests/go-resolution.browser.mjs` for real UI checks at 100 and 2,500 findings.

Final deployed-browser validation passed for `GO:0005730`: **100 findings in
7.9 seconds**, **2,500 findings in 59.1 seconds**, with all choice rows and
reference gene annotations present, no timeout and no browser errors. All 15
adapter tests passed again in the deployed Python/SQLite runtime.

### Full NCBI species ordering

20 Node and 18 Python checks passed. All 5,486 species resolve against the pinned
NCBI snapshot (14 merged IDs, zero unresolved). The catalog test verifies every
NCBI clade forms a contiguous block, not merely a handful of example families.
Checksum, parent-lineage/merge and missing-ID fixtures pass; saved-result tests
verify counts/statuses remain aligned and v11 snapshots are not changed.
`tests/ncbi-taxonomy.browser.mjs` passed on the deployed main service: real NPM1
profile, correct NCBI row order, reversed saved-v13 migration, all original count
values retained by species ID, mobile layout, no browser errors.

### Batched list / rectangle zoom / species exports

21 Node and 21 Python tests passed, with the Python suite repeated in the
production runtime. Tests cover two indexed local batch-query kinds, distinct
per-input matches, four simultaneous online fallbacks and round-robin caps.
The exact 40-gene user fixture retained every input after deployment; the 0.16s
browser rerun used the existing completed-job cache, not a cold SQL lookup.
`batch-area.browser.mjs` passed Shift/button/reverse rectangle zoom, Escape
cancellation, count preservation, species text download/MIME and mobile layout.
Visible rows changed from 2,320 to 247 after zoom. Static lists contain 2,320 /
5,486 exact row names and 2,293 / 5,382 unique NCBI species-rank names, including
Homo sapiens and Canis lupus, with no headers or tabs in the text lists.

### TimeTree lengths / dated cohorts

23 Node and 25 Python checks passed; the Python suite also passed inside the
actual deployed runtime. Unit tests cover the export's punctuation, two tiny
negative edges, unary-edge summation, exact known pairwise distances in real
level trees, null undated grafts, conservative exclusions and topology fallback.
SVG tests distinguish length-scaled coordinates from uniform depth, preserve
unknown edge nulls and verify dashed/† notation plus a Myr scale. Saved migration
checks retain complete rows and recompute coverage after exclusions.

`tests/timetree.browser.mjs` passed against main: 4,700-row NPM1 profile,
3,274 exported tips / 1,426 undated placements / 786 exclusions; real time-scaled
geometry, dashed inferred edges and dated SVG export. An old 5,486-row v13
fixture migrated without querying and retained each surviving species' original
counts. Mobile and browser error checks passed. Five levels without dates retain
explicit NCBI topology; no branch lengths are fabricated for them.

### OrthoDB evolutionary statistics

24 Node and 27 Python checks passed, including release-separated caches, strict
group identity checks, partial failures, zero/missing values and an independent
metadata lane that permits profile analysis to finish during metadata loading.
`tests/orthodb-stats.browser.mjs` passed against deployed main: live v13 group
6005769at2759 returned rate 2.5192, median protein length 712 aa, SD 45.6 aa and
median exon count 8. Expanded details retained exon SD 0 and source coverage;
metadata did not enter query history. PANTHER columns stayed isolated, mobile
layout passed, and no browser errors occurred.

### Typed queries and presets

30 Python and 24 Node tests passed. Added namespace/table parsing checks and a
strict-symbol regression verifying that multiple exact groups are retained and
missing symbols never invoke remote description search. The supplied 799-line
gene table parses into 794 unique symbols. Live `tests/query-types.browser.mjs`
passed: BRCA2 and NPM1 resolve to v13 groups, all exact groups are selected, a
missing symbol remains explicit, Polycomb/nucleolus presets populate correctly,
and mobile layout has no horizontal overflow or browser errors.

### Experimental shared-loss scoring

Focused checks cover increasing rewards for 1–6 independent exact holes, one
ancestral absence counted once, smaller clade preference, shorter-edge and
evolutionary-rate effects, unmatched-hole penalty, unequal overlapping holes,
unknown/pending exclusions, no losses outside inferred origin, missing-rate
reporting, species-row permutation and branch-unit invariance.
`tests/loss-score.browser.mjs` passed against main: three-hole pair ranks first,
neutral-rate fallback is explicit, branch details show lengths, Pearson remains
visible, and mobile has no overflow or browser errors. A synthetic 1,000-group
× 165-species host benchmark took 1,003 ms (17,069 inferred events, 85,710
positive pairs, top 100 retained). This verifies implementation behavior, not
biological predictive accuracy.

### Adaptive taxonomic clades

34 JavaScript tests passed, including real Eukaryota/Metazoa/Fungi/Viridiplantae
catalogs, disjoint label selection, exact descendant-set naming, unchanged branch
lengths, mixed-node rejection and named/colorized SVG exports.
`tests/taxon-clades.browser.mjs` passed on deployed main across those four levels,
with finer labels after zoom/pan, matching full-name key and mobile overflow/error
checks. Visual inspection led to a wider overview branch gutter for readable names.
