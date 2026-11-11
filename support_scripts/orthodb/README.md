# OrthoDB v13 downloads

Download the reference tables for a separate v13 database build:

```sh
python3 support_scripts/orthodb/download_v13.py \
  --destination /home/ilnitsky/OrthoDB_loads_v13 \
  --proxy socks5h://127.0.0.1:10808 --jobs 2
```

The command resumes `.part` files and verifies each completed file against the
official index's MD5. Only verified files receive their final names.
`download-status.json` records per-file status, sizes, hashes and sample column
counts. Re-running the command verifies existing completed files and resumes
unfinished ones. A destination lock prevents concurrent runs.

| Table | Why keep it |
| --- | --- |
| `genes` | Names, synonyms, UniProt mappings and gene metadata |
| `gene_xrefs` | Additional identifiers and external database mappings |
| `OG2genes` | Orthogroup membership |
| `OGs` | Orthogroup IDs, taxonomic levels and descriptions |
| `species` | Organism IDs, names and genome information |
| `levels` | Taxonomic levels and names |
| `level2species` | Taxonomic hierarchy and organism membership |

These archives total approximately 13.2 GB according to the official listing.
Sequence FASTA/CDS archives, OG hierarchy pairs and OG annotation cross-references
are not downloaded by this command; the current application does not require
their bulk dumps. Its NCBI BLAST workflow is separate from an OrthoDB sequence
database.

Sources:
- https://data.orthodb.org/v13/download/odb_data_dump/
- https://data.orthodb.org/v13/download/odb_data_dump/README.txt

Downloading is **not a migration**. Keep the live `/PANTHERDB/orthodb.db` intact.
Read the downloaded README before adapting the older importer: its `gene_names`
mode expects a preprocessed two-column input, not the full v13 genes table.
Stream gzip inputs when building a separate database to avoid storing full
uncompressed copies. Record the release in the new database, align all online
lookups and links, and separate release-specific caches before switching the app.
OrthoDB gene/group IDs are not stable between releases.

## Build a database with the existing schema

`stream_v13.go` uses only Go's standard library. Compile it to `bin/stream_v13`:

```sh
mkdir -p support_scripts/orthodb/bin
go build -o support_scripts/orthodb/bin/stream_v13 support_scripts/orthodb/stream_v13.go
python3 support_scripts/orthodb/test_build_v13.py
python3 -u support_scripts/orthodb/build_v13.py \
  --source /home/ilnitsky/PANTHERDB/orthodb.db \
  --archives /home/ilnitsky/OrthoDB_loads_v13 \
  --output /home/ilnitsky/PANTHERDB/orthodb_v13.db \
  --streamer support_scripts/orthodb/bin/stream_v13
```

The Python coordinator copies the three table definitions, all explicit indexes,
and the configured taxonomy levels from the read-only reference. The Go process
streams gzip input into SQLite batches, using the original packed integer gene
IDs. It uses v13 genes columns 1, 5 and 7 directly; multiple UniProt mappings get
separate rows, blank mappings become NULL, and entirely unmapped genes are omitted.
Mapped-only v13 `u_...` IDs are excluded from genes and memberships because they
cannot fit the unchanged legacy packed-ID encoding (some organism suffixes exceed
8 bits). Stage statistics record the excluded counts. This database covers the
legacy-compatible clustered identifiers, not every mapped-only v13 identifier.
It imports group memberships only for configured levels, as the original importer
does. Missing v13 levels are reported while their compatibility definitions remain.

There are no uncompressed staging tables/files. Indexes are built after loading;
SQLite may use temporary disk space during sorting. The unpublished `.building`
database disables journaling/synchronous writes for bulk loading. An interrupted
build must not be reused or substituted for the live database.

The final filename appears only after ANALYZE, exact schema comparison, SQLite
`quick_check`, imported-row count checks, and representative UniProt/group lookups.
This is not a full `integrity_check` of every index entry. The `.build.json` sidecar
records release, source hashes, per-stage timing/counts, missing levels and checks.
The builder refuses to overwrite either an existing output or staging database.
It never changes the live DB or switches the application's API/cache version.

`--resume-genes` is a narrow recovery option for the known, clean gene-parser
failure. It requires matching verified input hashes, matching tables with no
explicit indexes, no imported memberships, matching levels and a successful
SQLite quick_check. It counts committed rows and rescans the gzip prefix without
reinserting them. It is not a general resume option for crashes, index failures,
or arbitrary interrupted databases. Do not remove or replace the live database.

`--resume-validation` continues only a terminated read-only recovery validation
whose report still has no ingestion stages. It applies the same schema, input,
level and SQLite checks before writing any new rows.

The current long-running build uses the detached Docker container
`orthodb-v13-build`, so it is independent of interactive command sessions:

```sh
docker logs --tail=20 orthodb-v13-build
docker stats --no-stream orthodb-v13-build
```

Do not run a second builder against the same staging file. A running validation
does not yet have a percentage; row and archive progress resume after it finishes.

## Repair the completed candidate's identifier mappings

The first real v13 build imported 74,824,521 summary gene rows and 443,783,953
memberships and built all six indexes. Validation correctly stopped publication:
the genes summary's preferred UniProt/name columns did not supply the canonical
human accessions/names required by the app. The official v13 API maps Q9UL18 to
Argonaute group `8905661at2759`, while that lookup failed in the candidate.

`repair_v13_mappings.py` streams the dedicated **gene_xrefs** dump through the
Go streamer's `xrefs` mode into a disposable mapping database. It preserves initial
UniProt mappings, adds all UniProt aliases from the xrefs, deduplicates aliases,
and uses `NCBIgenename` records as authoritative names. Initial summary names are
retained only where the dedicated xrefs provide no gene names. Name-only genes
are retained. Alias/name combinations follow the legacy join representation;
presence queries must continue counting distinct `orthodb_id` values.

The completed membership table and its three indexes are preserved. The repair
replaces only `genes` and its three indexes in **one SQLite transaction**, with
rollback journaling and full synchronization. The scratch phase alone uses fast
disposable SQLite settings. Temporary sorting files live beside the candidate so
disk checks cover staging, sorting, the rollback journal and index construction.

Before applying mappings it checks four real human accession/symbol pairs and
their Eukaryota memberships. After applying, it checks the exact reference schema,
gene/membership row counts, the same sample mappings and SQLite quick_check.
Only then does it publish the **new** `orthodb_v13.db` filename. The live
`orthodb.db` and app/API release configuration are unchanged.

```bash
# Compile the updated streamer using local Go or the cached Go build image.
go build -o support_scripts/orthodb/bin/stream_v13 support_scripts/orthodb/stream_v13.go

# Fixture coverage includes real streaming, alias deduplication, fallback/name-only
# records, unchanged live data/schema/memberships and rollback after injected failure.
python3 -m unittest discover -s support_scripts/orthodb -p 'test_*v13.py' -v

# Run only against the known failed, unpublished, fully indexed candidate.
python3 -u support_scripts/orthodb/repair_v13_mappings.py \
  --source /home/ilnitsky/PANTHERDB/orthodb.db \
  --archives /home/ilnitsky/OrthoDB_loads_v13 \
  --output /home/ilnitsky/PANTHERDB/orthodb_v13.db \
  --streamer support_scripts/orthodb/bin/stream_v13 \
  --expected-ago-group 8905661

# Current detached repair job; independent of the exited original builder.
docker logs --tail=20 orthodb-v13-mapping-repair
docker stats --no-stream orthodb-v13-mapping-repair
cat /home/ilnitsky/PANTHERDB/orthodb_v13.db.repair.json
df -h /home/ilnitsky/PANTHERDB
```

The report records raw xref row counts/types, human sample hits, repair stages,
timings and final validation. The `.mapping.sqlite` file remains for audit.
`--resume-staged` is limited to a completely prepared mapping file with an
unchanged candidate/input identity before apply. It is not a general recovery
option for interrupted scratch imports or arbitrary candidate changes. Do not
launch another repair against the same files while the detached job is running.

## Gene-symbol recovery when the v13 archive has no NCBIgenename records

The actual downloaded v13 xref archive contains 38,025,313 `NCBIgid` records but
zero `NCBIgenename` records, despite the generic README listing that type. The
first alias repair recovered familiar UniProt accessions and safely stopped at
symbol validation; its completed `u`/`n` staging remains reusable.

`complete_v13_symbols.py` streams those GeneID links, downloads NCBI's daily
`https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_info.gz`, and joins by **GeneID plus
exact species taxid**. It uses explicit primary/authority symbols; descriptions
are never treated as gene names. Unofficial synonyms are retained in the source
but are not expanded into the legacy three-column table, limiting row growth.
Missing/retired GeneIDs and taxid disagreements are counted rather than guessed.
The daily NCBI source date/length and a local SHA-256 are recorded; this supplements
v13 annotations with current NCBI nomenclature, rather than claiming a frozen v13
symbol release. Resume rejects a changed daily source.

Existing v13 UniProt aliases and membership indexes are reused. A separate
`orthodb_v13.db.symbols.sqlite` holds prepared replacement genes; reusable aliases
are retained for retries. Candidate genes and their indexes are changed in one
rollback-protected transaction only after the human examples and independent
v13 AGO1 group check pass. Schema equality, membership count and quick_check gate
publication. The live `orthodb.db` is never replaced.

```bash
# Run only once; the detached orthodb-v13-symbol-repair job already runs this.
python3 -u support_scripts/orthodb/complete_v13_symbols.py \
  --source /home/ilnitsky/PANTHERDB/orthodb.db \
  --archives /home/ilnitsky/OrthoDB_loads_v13 \
  --output /home/ilnitsky/PANTHERDB/orthodb_v13.db \
  --streamer support_scripts/orthodb/bin/stream_v13 \
  --sources /home/ilnitsky/PANTHERDB/orthodb_v13_symbol_sources \
  --proxy socks5h://127.0.0.1:10808

# Observe progress; do not run a second repair concurrently.
docker logs --tail=20 orthodb-v13-symbol-repair
cat /home/ilnitsky/PANTHERDB/orthodb_v13.db.repair.json

# Six fixtures, including exact taxonomy, source protection, schema preservation,
# completed-alias reuse, sample validation and rollback after an injected failure.
python3 -m unittest discover -s support_scripts/orthodb -p 'test_*.py' -v
```

The detached job uses the existing worker image with its entrypoint overridden,
a 1 GiB memory cap and 1.5 CPU quota. Archives and the live database are mounted
read-only. Download/streaming, symbols and validation have separate checkpoints.
An interrupted `mapping_ready` stage can use `repair_v13_mappings.py --resume-staged`;
it honors the recorded prepared symbols file. Earlier committed symbol stages
can be reused by rerunning the symbol recovery after inspecting the failure.

### Lock recovery and accurate matching progress

A long external read-only COUNT on active DELETE-journal staging held a read lock
and made a symbol-batch commit exceed SQLite's default timeout. Imports and prior
committed symbol batches were preserved. Staging now uses WAL and a five-minute
busy timeout; neither live nor candidate journaling is changed by that setting.
Regression fixtures hold a reader snapshot while symbol commits proceed.

Each matching batch now commits a compound `(GeneID, packed OrthoDB ID)` cursor
and counters in the same transaction as its symbol inserts. Further interruptions
resume from that cursor. The first recovery from the older, uncheckpointed pass
replays its input and reuses existing symbols with INSERT OR IGNORE; it does not
reload the 74,130,707 NCBI records or the 38,025,313 unique GeneID links. Completed
NCBI archives are reused after local SHA-256 validation without contacting the
mutable daily endpoint again.

Progress reports `sources_checked / total_links`, matched links, mismatches,
unresolved links and existing symbol hits. Exact-species matches are an outcome,
not the denominator: some source links cannot match. Read the JSON report/logs
for progress, rather than running COUNT/join queries on active build databases.
The failed container's original logs remain under
`orthodb-v13-symbol-repair-lock-failure`; the resumed job retains the normal name.

Eleven importer/repair fixtures now cover the full pipeline, concurrent staging
readers, interruption/resume without missing or duplicating symbols, and reuse of
pinned input without network access.

The worker uses SQLite 3.27.2: `BEGIN IMMEDIATE` attempts to write-lock an
attached read-only prepared database and fails before changing the candidate.
Apply uses a deferred transaction, acquiring the candidate write lock on the
first index change while retaining atomic rollback and the read-only source.
`--resume-staged` also accepts this exact pre-write failure only when the
candidate/input identity still matches. It reuses the validated `.symbols.sqlite`
table without downloading or matching again. Run repair tests in the worker
image as well as on the host; newer host SQLite does not reproduce this failure.
The failed container logs are preserved as
`orthodb-v13-symbol-repair-readonly-failure`.

## Missing v13 orthology levels

The original membership import retained the 160 legacy level IDs. The v13
catalog has nine additional eukaryotic levels with OGs: SAR, Discoba, Metamonada,
Haptista, Cryptophyceae, Amphibia and three Plasmodium subgroups. The offline
`build_v13_levels.py` filters only these levels from the verified membership
archive into an independent, indexed, integrity-checked supplement. It verifies
the archive MD5, main DB identity and every requested level before atomic
publication. The main DB is opened read-only throughout.

```sh
python3 -u support_scripts/orthodb/build_v13_levels.py \
  --base /home/ilnitsky/PANTHERDB/orthodb_v13.db \
  --archives /home/ilnitsky/OrthoDB_loads_v13 \
  --catalog web/public/data/trees-v13.json \
  --streamer support_scripts/orthodb/bin/stream_v13 \
  --output /home/ilnitsky/PANTHERDB/orthodb_v13_levels.sqlite
# Running detached build on this host:
docker logs -f --tail 30 orthodb-v13-extra-levels
```

`web/build_v13_trees.py` separately generates matching taxonomy trees/cohorts
from verified metadata; runtime `v13_catalog.py` projects compact reference trees
onto v13 representatives. No synthetic Protista/Spiralia OG level is invented.
The runtime attaches only a completed supplement whose manifest agrees with the
base DB; release/path/stat fingerprints invalidate caches after publication.

### Bulk v13 evolutionary rates (SPARQL)

`fetch_v13_metadata.py` extracts release-verified v13 rate and gene-architecture
metadata from https://sparql.orthodb.org/sparql. The ordinary v13 flat-file dump
and `/og_description` do not include evolutionary rates. The SPARQL frontend
advertises release 13.0; the builder checks that banner and the known v13 group
6005769at2759 rate 2.5192 at startup/resume and every 50 pages. The schema's older
ontology documentation alone is not used to establish the data release.

The detached container is `orthodb-v13-metadata-bulk`; output is ignored local
reference data in `local_data/orthodb-v13-metadata/` (relative to repository root).
It starts with Eukaryota, Metazoa, Fungi and Viridiplantae, then other v13 levels.
Only groups having an upstream rate are included; absent rates are not zero.
Source list contains 990 levels / 17,782,378 groups, which is an upper bound on
rate rows, not a verified count of available rates. Never label that denominator
as exact rate-completion progress.

```sh
# From repository root:
docker logs -f --tail 20 orthodb-v13-metadata-bulk
watch -n 5 cat local_data/orthodb-v13-metadata/progress.json
# Resume the same stopped/failed container (completed pages are retained):
docker start orthodb-v13-metadata-bulk
# Explicit stop; the active uncommitted page can be retried on resume:
docker stop orthodb-v13-metadata-bulk
```

A single worker requests pages of 5,000 groups in stable URI order using keyset
pagination, waits between pages, retries errors with backoff, and rejects
endpoint truncation headers, malformed numbers, incorrect levels and repeated
or unordered cursors. Rows and cursor checkpoints commit in one SQLite
transaction; a single-writer lock prevents duplicate jobs. Progress JSON is
replaced atomically. The final stage runs SQLite quick_check and creates a level
index. The live reference database and application deployment are untouched.

`metadata.sqlite` contains:
`metadata(group_id, level, rate, median_length, length_sd, median_exons, exon_sd)`,
`levels(level, name, cursor, rows, complete)`, and `provenance(key, value)`.
Read it using SQLite URI `mode=ro`; the downloader uses WAL during construction.
A consumer must inspect progress/provenance and handle groups not downloaded yet.
Do not rename this partial file into a production reference or claim all rates
are present until the completion marker and checks pass.

```sh
sqlite3 -readonly local_data/orthodb-v13-metadata/metadata.sqlite \
  "SELECT group_id,rate,median_length FROM metadata WHERE group_id='6005769at2759';"
```

Focused validation:
`python3 -m unittest discover -s support_scripts/orthodb -p 'test_fetch_v13_metadata.py' -v`.
