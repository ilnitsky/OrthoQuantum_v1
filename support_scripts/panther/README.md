# PANTHER v19 candidate update

This pipeline downloads **pinned v19 sources**, builds a separate validated bundle
at `/home/ilnitsky/PANTHERDB/panther_v19/`, and leaves the live
`/home/ilnitsky/PANTHERDB/panther.sqlite` unchanged.

## Sources and retained meaning

- Classification files: https://data.pantherdb.org/ftp/sequence_classifications/19.0/PANTHER_Sequence_Classification_files/
- Ortholog/paralog archives: https://data.pantherdb.org/ftp/ortholog/19.0/
- Relationship format notes: https://data.pantherdb.org/ftp/ortholog/19.0/README
- Matching tree and species metadata: https://data.pantherdb.org/PANTHER19.0/globals/

The actual v19 relationship rows have **five fields**: gene, other gene,
relationship type, reported ancestor/range, and PANTHER family. The format README
lists the first four. All five are retained. `LDO` and `O` remain distinct;
`P` records come from the separate AllParalogs archive. No orthology is inferred
from shared families/subfamilies, and no transitive links are invented. Xenolog
archives are outside this update.

The classification catalog contains **143 files covering 144 tree species**:
`PTHR19.0_green_algae` contains both KLENI and CHLRE. Metadata also includes three
unused ASHGO/BRARP/ENTHI aliases; these are recorded but are not grafted onto the
144-leaf v19 tree. Genome coverage is checked from imported rows, not file count.
The official NHX file has no final semicolon; the parser accepts that complete
rooted tree while still rejecting unclosed clades and trailing garbage.

Downloads check HTTP metadata/length and retain local SHA-256 provenance. These
are locally computed hashes, not publisher-supplied signatures/checksums. Tar.gz
streams are drained through EOF to verify their gzip CRC/trailers; tar members
are read as streams, never extracted into arbitrary filesystem paths.

## Bundle

| File | Purpose |
| --- | --- |
| `panther.sqlite` | Original 13-column `panther` table and legacy indexes; additional UniProt and genome/UniProt indexes |
| `relationships.sqlite` | Normalized gene keys, ortholog/paralog edges, ancestor and family dictionaries; indexed for either endpoint |
| `PANTHER.xml` | Matching 144-species phyloXML tree, using actual taxids for leaf IDs |
| `prottree_id_converter.csv` | Matching genome-code to tree-ID map |
| `tree.json` | Optional equivalent template for the lightweight viewer; its loader also supports the XML directly |
| `species_list.tsv`, `species_pthr19_annot.nhx` | Original pinned species metadata/tree |
| `manifest.json` | Release, source URLs/headers/hashes, counts, examples and validation results |

Long repeated gene identifiers in relationship rows are represented by integer
keys. Lookup identity is `genome code + UniProt accession`, so differing auxiliary
HGNC/database tags do not discard valid pair matches. The original classification
identifier is retained. Pair endpoints absent from classification records are
preserved and counted in the report. Their genome codes must still belong to the
versioned species tree.

Reported pair direction/type is retained in storage; indexed lookup checks both
endpoints. Source duplicates are retained as reported; presence/count views use
distinct target genome/accession pairs to prevent inflation.

## Commands

From `/home/ilnitsky/best_repository_ever`:

```bash
# Compile the standard-library Go tar/gzip/relationship streamer.
mkdir -p support_scripts/panther/bin
# Use local Go if installed:
go build -o support_scripts/panther/bin/panther_relations support_scripts/panther/relations.go
# Or use the cached Go image:
docker run --rm --user "$(id -u):$(id -g)" \
  -e GOCACHE=/tmp/go-cache -e GO111MODULE=off -e CGO_ENABLED=0 \
  -v /home/ilnitsky/best_repository_ever:/src -w /src \
  golang:1.18.0-bullseye go build \
  -o support_scripts/panther/bin/panther_relations support_scripts/panther/relations.go

# Fixtures: schema/ID compatibility, NHX and aliases, real tar/gzip streaming,
# LDO/O/P separation, reverse lookup, source preservation and CRC rejection.
python3 -m unittest discover -s support_scripts/panther -p 'test_*.py' -v

# Direct invocation: downloads first, then waits for the active OrthoDB repair
# before starting heavy SQLite writes. Never run alongside the named job below.
python3 -u support_scripts/panther/build_v19.py \
  --downloads /home/ilnitsky/PANTHERDB/panther_v19_downloads \
  --output /home/ilnitsky/PANTHERDB/panther_v19 \
  --reference /home/ilnitsky/PANTHERDB/panther.sqlite \
  --streamer support_scripts/panther/bin/panther_relations \
  --proxy socks5h://127.0.0.1:10808 \
  --wait-for-orthodb /home/ilnitsky/PANTHERDB/orthodb_v13.db.repair.json

# Monitor the detached job that is already running.
docker logs --tail=20 panther-v19-build
docker stats --no-stream panther-v19-build
cat /home/ilnitsky/PANTHERDB/panther_v19.build.json
df -h /home/ilnitsky/PANTHERDB
```

The detached job is `panther-v19-build`, using a standard-library Python adapter
from the existing worker image with its normal entrypoint overridden. It has a
1 GiB memory cap and 0.75 CPU quota. Its live database mounts are read-only.
Downloads can resume `.part` files when source headers are unchanged. A failed
partially built SQLite bundle is not blindly reused/overwritten.

The relationship archives contain approximately 15.7 GB of ortholog text and
2.5 GB of paralog text before compression. They are streamed; there is no
uncompressed text staging copy. SQLite sorting space is placed beside the
candidate and free-space checks preserve a reserve.

## Validation and publication

### Interrupted relationship import

`recover_v19.py --root /PANTHERDB --streamer /builder/bin/panther_relations`
recovers a build with a completed classification checkpoint and an interrupted
relationship import. Run with the same data and read-only builder mounts as the
original job, as the owner of the candidate files. It verifies every downloaded
source against the recorded SHA-256, rechecks classification integrity, counts,
species and demo mappings, and builds relationships in a new timestamped staging
directory. The original `.building` directory is preserved: its relationship DB
cannot be trusted after interruption with journaling disabled. Publication still
requires the normal relationship checks and atomically renames the whole bundle.
The recovery report remains `panther_v19.build.json`.

The November 10 recovery container is `panther-v19-recovery-2` (2 CPUs, 2 GiB
memory); the original `panther-v19-build` exited with code 255 without a logged
parser/Python error or an OOM flag. Monitor recovery with:

```sh
docker logs --tail=20 panther-v19-recovery-2
cat /home/ilnitsky/PANTHERDB/panther_v19.build.json
```

The pipeline checks classification column compatibility and exact active-genome
coverage, known human accessions/symbols (including AGO1) and SESN2, normalized
relationship counts/types and endpoint/dictionary integrity, an AGO1-to-mouse
ortholog example, indexes, ANALYZE and SQLite quick_check. It atomically renames the
whole staging directory only after validation. This does not replace the live DB
or claim a full SQLite integrity_check.

## Separate test-site integration

The lightweight test site's `PANTHER_BUNDLE_DIR=/reference/panther_v19` setting is
an explicit opt-in to this candidate. Until the complete manifest exists it uses
the existing local PANTHER data. After publication and a page refresh it loads the
v19 database **and matching tree/map together**. Cache identity includes the bundle
manifest and DB files, avoiding reuse of older-release query results.

Its PANTHER selector supports subfamilies, LDO-only orthologs, or LDO+O orthologs.
The ortholog views count direct, distinct target genes; they exclude `P` edges.
The reference-genome cell marks the input gene itself, not self-orthology. The old
minimum-nine-record subfamily display rule is not applied to direct orthologs.

Production Dash/worker configuration remains unchanged. A production cutover must
coordinate the database, tree/map and release-specific result cache; copying only
the SQLite file would not complete the migration.
