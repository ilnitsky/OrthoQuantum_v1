-- 0at100953       111167_1:000002
-- 0at100953       1123958_1:00001c
-- 0at100953       114102_1:000001
-- 0at100953       114430_1:000014
-- 0at100953       1193422_1:000016
-- 0at100953       129875_1:000005
-- 0at100953       129951_1:000004
-- 0at100953       129953_1:00000c
-- 0at100953       129956_1:000005
-- 0at100953       130308_1:000003
.echo on
.output
DROP TABLE IF EXISTS orthodb_to_og;

CREATE TABLE orthodb_to_og (
    orthodb_id INTEGER NOT NULL,

    cluster_id INTEGER NOT NULL,
    clade INTEGER NOT NULL
);

.mode csv
.separator \t
.import /tmp/import_data.tab orthodb_to_og

CREATE INDEX orthodb_to_og_orthodb_id_idx ON orthodb_to_og(orthodb_id);
CREATE INDEX orthodb_to_og_clade_idx ON orthodb_to_og(clade);
CREATE INDEX orthodb_to_og_clade_cluster_id_idx ON orthodb_to_og(clade, cluster_id);

CREATE TABLE levels (
    level_id PRIMARY KEY NOT NULL,
    scientific_name TEXT NOT NULL
);

INSERT INTO levels VALUES
    (2759, "Eukaryota"),
    (4751, "Fungi"),
    (7742, "Vertebrata"),
    (7898, "Actinopterygii"),
    (8782, "Aves"),
    (33090, "Viridiplantae"),
    (33208, "Metazoa"),
    (199999999, "Protista")
;

VACUUM;
ANALYZE;

-- Docker commands
-- docker run -it --rm --user "$(id -u):$(id -g)" --entrypoint bash -v $PWD:/wd --workdir /wd nouchka/sqlite3
-- ./scripts/tabprocessor OG2genes odb10v1_OG2genes.tab

.mode box
.headers on
.timer on

SELECT
    *
FROM genes
LEFT JOIN orthodb_to_og USING (orthodb_id)
WHERE
    uniprot_id = "Q92484" AND
    clade=7742
;

