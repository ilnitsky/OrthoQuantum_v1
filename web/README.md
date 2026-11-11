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
  families require a choice. Family profiles retain every named subfamily,
  including rare assignments, and merge SF IDs sharing the same name. A previous
  dataset remains in local history.
- Annotated phyloXML import, full dataset JSON import/export, count-matrix CSV
  import/export, correlation CSV, a PNG of the **visible viewport**, and a complete
  SVG image with readable names/counts and the current species filter/column order.
- Fifteen datasets retained in browser IndexedDB; newest ten shown. Imported files
  are parsed locally and are not uploaded to the server.

## Important scientific/feature boundaries

This implementation does not yet have complete scientific parity with legacy Dash.

- Branches show **topology only**, not branch-length-scaled evolutionary distances.
- Cluster ordering and **Gene copy counts** are the profile display defaults.
  Correlations always use binary presence (zero versus one-or-more), independent
  of that display setting. Average-linkage clustering uses distance **1 − r**
  from the same binary Pearson matrix; constant profiles are undefined and last. Species search filters the viewport
  and whole SVG image; dataset JSON/CSV and correlations retain all species.
- Fit whole plot compresses both axes and automatically hides species labels below
  12 pixels per row and column labels below 8 pixels per column. Subpixel cells
  aggregate status with findings taking priority. Hover shows the cell under the
  pointer; use normal spacing or SVG for exact inspection. Whole SVG uses readable
  spacing and avoids raster canvas dimension limits; exceptionally large vector
  files can still be demanding for external image viewers.
- Correlations/clustering include all loaded groups, up to **2,500**. Packed binary
  profiles and quadratic nearest-neighbor-chain average linkage run in a Web Worker.
  The correlation clustermap orders both axes by the same average-linkage tree
  and draws matching dendrograms. Wheel/buttons zoom; drag pans; Fit restores the
  complete matrix without scrollbars. Query order is available separately.
- Fresh lookups build up to 2,500 profiles; Max findings defaults to 100
  and accepts 1–2,500 total matches. Broad searches report truncation instead of claiming complete results.
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

## Correlation clustermap

Both axes default to average-linkage ordering using **1 − binary Pearson r**;
matching dendrograms show that hierarchy. Gene-copy magnitudes never affect the
correlations: 0 means absent, and any positive count becomes 1. The profile
display mode changes only the phylogenetic profile. Constant profiles have
undefined correlations, remain gray and are appended after clustered profiles.
The zero-centered palette is blue (−1), white (0), red (+1). Clustering now includes all loaded groups (up to 2,500); see the full-dataset update below.

Use the mouse wheel or +/− buttons to zoom, drag to pan, and Fit/double-click/zero
to reset. Labels appear as cells become large enough; hover always gives full
group names and the correct reordered cell value. The square plot fits its card
without nested scrollbars. Orthogroup/PANTHER view switching retains its order
and zoom/pan position. Browser interaction check:

```bash
PLAYWRIGHT_MODULE=/tmp/ortho-lite-browser/node_modules/playwright/index.mjs \
  node web/tests/clustermap.browser.mjs
```

Correlation cells display coefficients to two decimal places once zoom makes the
cells large enough. Text switches between black and white for contrast; undefined
values show an em dash. Hover retains five-decimal precision. Fit hides the
numbers again when the matrix is dense.

## My queries and the complete Help/About guide

The header's **My queries** menu lists this browser's queued, running, ready,
failed and cancelled jobs, including queue positions and current progress. Open
an entry to resume watching it or recover its result; Cancel affects that job.
**New query** and Reset detach the current view and leave earlier work running.
The newest ten records are shown, with fifteen retained locally. Configuration
lookups are internal and do not clutter this list. Only completed results are
shared by the server cache; running jobs remain independent, so cancelling one
query cannot cancel another user's identical active request.

Completed datasets opened by this browser also remain in IndexedDB. The job menu
can open those local saved results without rerunning work, including after the
server result expires. Live jobs themselves use the current main server's
in-memory queue; a server restart expires unsaved jobs/results, and finished
server results normally expire after one hour. Legacy Redis queries remain with
the separate legacy service; they are not silently merged into the new queue.

**Help / About** opens `/about` in a separate tab so the active plot remains in
place. It preserves the original guide's complete text and all ten tutorial PNGs,
with a contents list and a brief note identifying legacy-only behavior. Rebuild
that static page from the legacy source without importing/executing Dash:

```bash
python3 web/export_legacy_about.py
```

New files: `public/jobs.mjs`, `public/about.html`, `public/tutorial/1.png` through
`10.png`, and the guide exporter. `/api/jobs/:id?summary=1` returns lightweight
status/position data; there is no global job-list endpoint. Header history uses
only capability IDs already known to the current browser.

## Named PANTHER family subfamilies

Choose **Family · named subfamilies** to see every subfamily name in a matched
PANTHER family, including paralogous groups. Direct LDO/All ortholog views still
contain only reported direct matches of each query protein; they intentionally
do not imply that other paralogous subfamilies are direct orthologs. Use the
**Compare named family subfamilies** button to switch the currently displayed
gene, or change the PANTHER selector while viewing its profile.

Family columns are grouped by the actual `Subfamily` name. Different SF IDs
with that same name share a column; IDs remain visible in the table/metadata.
The old minimum-nine-record cutoff has been removed. Missing names remain in
an explicit Unassigned column. Counts are distinct UniProt protein accessions
per genome/name (not a claim that every accession is a distinct genomic locus).
The binary presence view remains available. The family viewer supports up to
1,000 named columns. New v19 UniProt queries use the indexed v19 classification
directly; they do not depend on older OrthoDB name mappings. Reference-genome
scoping is applied when the selected organism is represented.

Verified NPM1 family PTHR22747 names in the published v19 data:

- GEO09167P1-RELATED: 11 proteins across 9 species.
- NUCLEOPHOSMIN: 61 proteins across 20 species, combining six SF IDs.
- NUCLEOPLASMIN CORE DOMAIN-CONTAINING PROTEIN: 7 proteins across 7 species.
- NUCLEOPLASMIN-2: 21 proteins across 18 species.
- NUCLEOPLASMIN-3: 22 proteins across 20 species.

Old saved subfamily results retain their original data; a **Refresh named family
subfamilies** button requests the current complete family view.

### Current main reference and larger queries

Root Compose selects validated `orthodb_v13.db` and the v13 search API. Its
publication sidecar must report complete, matching schema and quick_check ok.
Only available reference levels are offered; the curated species-tree topology
and cohorts remain fixed templates. Bundled demos remain labeled v11 snapshots,
separate from fresh v13 lookups. Profiles reject an explicit mismatched release.
See the root README for the paired v11 rollback overrides.

Max findings defaults to 100 and accepts 1–2,500, with a 20-million-cell profile
limit. Above 1,000 groups, correlation storage uses a packed Float32 upper
triangle (undefined constants stored as NaN), transferred from the worker without
copying. Average-linkage distances use a separate packed Float64 workspace.
All groups are clustered; only the top 30 pair records are retained for the pair
table, while CSV export reads all defined pairs from the correlation matrix.
Dense overviews rasterize at up to 2048 pixels; zoomed cells and hover use exact
matrix positions. Zoom extends to 1024×. The main container has a 1 GiB memory
ceiling / 512 MiB Node heap, 10 MB requests, 50 MB results and a 15-minute job
budget for paginated broad searches. Correlations are computed in the browser.

### Release-matched v13 species sets and levels

`build_v13_trees.py` reads the MD5-verified species, levels and level2species
archives. `public/data/trees-v13.json` contains 160 official eukaryotic levels
with nonempty OG definitions. Extended sets contain 5,486 current NCBI species
(5,768 source clustered genomes), 2,320 metazoans, 2,416 fungi, 410 green plants
and 93 lophotrochozoans. Alternate assemblies are collapsed to one representative
per NCBI species (lowest organism suffix, then source taxid); organism/assembly
IDs stay on rows and control count filtering. The 17 renamed taxonomy IDs are
resolved through the official species-to-organism mapping rather than fuzzy
name matching. Taxonomy paths yield polytomies, not inferred evolutionary branch
lengths. Compact old topologies are projected onto matching v13 organisms; the
resulting compact sets have 147 eukaryotes / 393 metazoans.

Common levels are promoted; remaining levels are alphabetical. The current
reference organism is retained when available, otherwise common organisms lead
the new species dropdown. A helper note identifies taxonomy vs curated trees,
the representative policy and available genome count. Expanded trees include
SAR, Discoba, Metamonada, Haptista, Amoebozoa, Alveolata, Stramenopiles, Euglenozoa,
Apicomplexa, Ciliophora, Rhodophyta and Cryptophyceae. OrthoDB v13 does not define
a separate Spiralia OG level; Lophotrochozoa uses its published level 1206795.

The initial main DB imported historical levels. Nine missing official levels
are provided by the separate `orthodb_v13_levels.sqlite` supplement, built with
`support_scripts/orthodb/build_v13_levels.py`. Its manifest must be complete,
quickCheck ok, release v13 and match the base file's size/mtime. It is attached
read-only; it never changes the main v13 DB. Node cache fingerprints include
both supplement and manifest. Until publication, unavailable levels are omitted.

```sh
# Rebuild taxonomy assets offline from the verified release metadata.
python3 web/build_v13_trees.py --archives /home/ilnitsky/OrthoDB_loads_v13 --output web/public/data/trees-v13.json
# Follow the independent missing-level import; do not COUNT active build files.
docker logs -f --tail 30 orthodb-v13-extra-levels
```

### SQL budgets and broad GO resolution

Each SQL statement has a 120-second budget, reset on execute. Network waits and
previous statements cannot consume the next statement's budget; the separate
15-minute overall job limit still applies. GO identifiers go directly to the
release-specific upstream search, which accepts pages of up to 1,000 results.
Reference-organism gene names are loaded once through the gene-ID index.
Memberships are then read and cached by contiguous orthogroup using the existing
clade/cluster index. Do not pre-scan all reference memberships via the gene index:
it needs scattered row reads across all ancestor levels and can exceed 120
seconds on the production dataset, even though it looks attractive on fixtures.
No live DB indexes are added and both reference databases remain read-only.

### Full NCBI taxonomy ordering

`build_ncbi_taxonomy.py` verifies the official taxdump MD5 and records SHA256,
then extracts only required taxa and ancestors from nodes.dmp, names.dmp and
merged.dmp. The pinned subset is `public/data/ncbi-taxonomy-v13.json` (13,200
nodes / 5,651 requested IDs). All 5,486 OrthoDB species rows resolve: 5,472 current
IDs and 14 merged IDs, no unresolved IDs. Original OrthoDB row/genome IDs stay
unchanged for membership queries; current NCBI IDs are separate metadata.

`ncbi_order.py` builds the full parent hierarchy, including genera, families,
orders and clades absent from OrthoDB's orthology-level paths. Sibling clades are
sorted by scientific name and traversed depth-first. Single-child scaffolding is
collapsed; relationships remain multifurcating and branch lengths have no
inferred evolutionary meaning. All species/count cohorts are unchanged. Compact
cohorts are now pruned from the same NCBI hierarchy rather than retaining the old
topology. Tests verify that every NCBI clade is one contiguous block.

Saved/imported v13 results without an NCBI snapshot are automatically reordered
by `public/taxonomy-order.mjs`, with complete count/status rows permuted by ID.
No biological query is repeated; old v11 snapshots retain their own tree.
Species outside the current catalog remain explicitly marked at the end, never
dropped. New results record the pinned NCBI archive source/hash in provenance.

```sh
# Download the official archive and its published MD5 into a scratch directory.
curl --fail --proxy socks5h://127.0.0.1:10808 https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz.md5 -o /tmp/ortho-ncbi-taxonomy/taxdump.tar.gz.md5
curl --fail --proxy socks5h://127.0.0.1:10808 https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz -o /tmp/ortho-ncbi-taxonomy/taxdump.tar.gz.part
# Extract a verified, compact taxonomy snapshot; do not commit the raw dump.
python3 web/build_ncbi_taxonomy.py --archive /tmp/ortho-ncbi-taxonomy/taxdump.tar.gz.part --checksum /tmp/ortho-ncbi-taxonomy/taxdump.tar.gz.md5 --catalog web/public/data/trees-v13.json --output web/public/data/ncbi-taxonomy-v13.json
python3 web/build_v13_trees.py --archives /home/ilnitsky/OrthoDB_loads_v13 --taxonomy web/public/data/ncbi-taxonomy-v13.json --output web/public/data/trees-v13.json
```

NCBI source documentation: https://www.ncbi.nlm.nih.gov/datasets/docs/v2/data-processing/taxonomy-processing/taxonomy/

### Batched inputs, selection zoom and species exports

Gene symbols and UniProt accessions resolve in at most two local indexed batch
queries, preserving each identifier's matches. Unresolved inputs use at most
four concurrent upstream requests; SQLite connections stay on the main adapter
thread. Result admission is round-robin across inputs so a broad alias such as
BRE cannot consume the global cap before later exact symbols. Annotations are
then loaded per unique selected group, with shared query provenance retained.

On the profile, Shift-drag over the heatmap selects a zoom rectangle. The
Select area to zoom toggle enables the same gesture without Shift. Ordinary
drag still pans; Alt-drag pans even with selection mode enabled. Reverse drags
are normalized; Escape/pointer cancellation leaves the view unchanged. The box
zooms rows/columns independently using the current scroll offsets and spacing,
with bounded readable cell sizes. Fit whole plot restores the overview.

Species list (.txt) exports every species in the loaded dataset, not only the
visible viewport. `export_species.py` also creates exact v13 row lists and
TimeTree lists in `public/data/species/`. TimeTree lists use unique current NCBI
species-rank names (subspecies/strains ascend to their species ancestor): 2,293
metazoan and 5,382 eukaryotic names. Exact lists retain 2,320 / 5,486 source rows.
TSV maps connect original row taxids/names to exported species names; no species
lack a species-rank ancestor. All text files have one name per line, no header.

```sh
python3 web/export_species.py
# Browser check: exact 40-gene user fixture, zoom, counts and exported text.
PLAYWRIGHT_MODULE=/tmp/ortho-lite-browser/node_modules/playwright/index.mjs LD_LIBRARY_PATH=/tmp/ortho-lite-browser/libs/root/usr/lib/x86_64-linux-gnu node web/tests/batch-area.browser.mjs
```

TimeTree input-format reference: https://timetree.temple.edu/faqs

### User-supplied TimeTree branch lengths

`build_timetree.py` reads the user Newick and unresolved-name report and derives
all level trees from one master. `timetree.py` handles the export's unquoted
colon/parenthesis labels, sums edges when pruning unary paths, and preserves
pairwise distances. Two tiny negative export edges (-0.00007/-0.00041 Myr) are
clamped to zero and logged. Larger negative/nonfinite lengths are rejected.

The input has 3,684 tips. 3,274 match current OrthoDB row names; 410 unrequested
extra tips are removed. Another 1,426 rows are placed near represented relatives
using current NCBI species/genus or a monophyletic represented family. These are
explicit polytomies at existing nodes, with `length: null`, not guessed divergence
ages. Unsupported placement excludes 786 rows from dated cohorts. The master
therefore displays 4,700 rows; Metazoa 2,046, Fungi 2,048, plants 384 and
Lophotrochozoa 76. Original gene/organism IDs remain unchanged.

155 of 160 official levels have dated coverage. Cryptosporidium, Eimeria,
Microsporidia, Sporidiobolales and Trebouxiophyceae retain clearly labeled NCBI
topology-only views; their dates are not invented. Compact views are induced
from the same master, preserving edge sums and reporting excluded counts.
`v13_catalog.py` uses the timed catalog only when its NCBI snapshot matches the
baseline. Cache fingerprints include both tree assets.

Canvas and whole SVG now use cumulative branch lengths (Myr), a time ruler, and
dashed/† marks for undated placements. Unknown edges remain null in datasets;
only their display endpoint is projected to the tip column. Tip detail reports
unknown time or the exported terminal branch. Source provenance records input
hashes, rounding corrections and placement policy. TimeTree may already have
made parent-taxon substitutions; the original UI asterisks are not encoded in the
provided Newick, so exported tips are not claimed to be independent measurements.

Old v13 results are safely reordered/pruned by complete rows when reopened,
without requerying retained counts. Correlations are recomputed when cohort
migration changes the data. Reports list every row's status and all exclusions.

```sh
python3 web/build_timetree.py --catalog web/public/data/trees-v13.json --taxonomy web/public/data/ncbi-taxonomy-v13.json --newick orthodb-v13-eukaryota-all.nwk --unresolved unresolved_species_timetree.txt --output web/public/data/trees-timetree-v13.json
# Audits:
cat web/public/data/trees-timetree-v13.report.json
# Plain exclusion list / full placement table:
# web/public/data/trees-timetree-v13.excluded.txt
# web/public/data/trees-timetree-v13.placements.tsv
```

### OrthoDB group statistics

The annotation table lazily loads release-matched evolutionary rate, median
protein length and length SD. More shows exon statistics and full source-group
coverage/copy counts. These source-wide values differ from selected-cohort
presence. Evolutionary rate is relative sequence divergence, not divergence per
Myr. Missing values show an em dash; zero values remain visible. PANTHER views do
not use OrthoDB statistics.

Metadata uses an independent job lane (`metadata_adapter.py` / `orthodb_stats.py`),
visible-row batches of at most 20 and a bounded seven-day release-specific cache.
It does not block the analysis queue or create My queries entries. Retry handles
partial source failures without rebuilding the profile.

## Query types and functional presets

Query type supports automatic mixed identifiers, exact gene symbols, UniProt,
GO, KEGG KO/pathway, InterPro, OrthoDB groups, other gene/protein IDs and free
text. Typed annotation lists validate their namespace. Up to 1,000 input lines
are accepted; Max findings remains independently capped at 2,500 (default 100).
Exact symbols use the selected reference organism's indexed local gene-name
mapping, never a description-search fallback. All exact groups are selected,
multiple-group mappings are flagged and missing symbols remain unresolved.
This is not a live HGNC authority/alias resolver: obsolete symbols may need
updating. Symbol mode accepts pasted tables by taking the first column.

Load demo and presets adds fresh GO:0005730 (nucleolus) and six editable human
symbol lists: remodellers, readers, writers, PRC1 + PRC2, histone erasers and
DNA methylation machinery. Presets are starter panels, not exhaustive catalogs;
they populate the form for review/submission. Existing bundled demos remain.

See [LOSS_MODEL.md](LOSS_MODEL.md) for the experimental branch-aware shared-loss
ranking, formulas, parameter meanings and scientific limitations.

## Adaptive taxonomic branch colors and labels

The profile tree now names clades using the pinned NCBI taxonomy instead of
numeric TimeTree internal labels. Only a taxon's exact monophyletic sampled
descendant set may label a branch; no reparenting or length changes occur.
Taxon colors derive deterministically from taxids. A non-overlapping frontier
of up to 12 visible clades adapts to viewport span and row spacing, so broad
cohorts and deeper orthology selections use appropriately sized groups.
Colored descendants, small white-backed labels at clade tops and a full-name
HTML key identify the active groups. Overview tree gutter widened for labels.
Undated edges retain dashes. Whole SVG export uses the same selection/color
logic over its full extent; visible PNG includes the drawn labels.
Implementation: public/taxon-clades.mjs, model/viewer/whole-image and app loading.
