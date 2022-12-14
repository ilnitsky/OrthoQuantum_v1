-- file: odb11v0_gene_xrefs.tab
-- docker run -it --rm --user "$(id -u):$(id -g)" --entrypoint bash -v $PWD:/wd --workdir /wd nouchka/sqlite3
-- ./tabprocessor gene_xrefs other/odb11v0_gene_xrefs.tab

-- docker exec -it c58cdca36a1b bash
-- sqlite3 orthodb.db <./scripts/1_uniprot.sql


-- 1000373_0:000000        374504755       NCBIproteinGI
-- 1000373_0:000001        374504763       NCBIproteinGI
-- 1000373_0:000002        374504767       NCBIproteinGI
-- 1000373_0:000003        374504758       NCBIproteinGI
-- 1000373_1:000000        RnQV1s4_gp1     NCBIgenename
-- 1000373_1:000000        11604942        NCBIgid
-- 1000373_1:000000        YP_005097973.1  NCBIproteinAcc
-- 1000373_1:000001        IPR001795       InterPro
-- 1000562_0:000000        WP_037594048.1  NCBIproteinAcc
-- 1000562_0:000001        IPR020097       InterPro
.echo on
.output

DROP TABLE IF EXISTS orthodb_to_uniprot;

CREATE TABLE orthodb_to_uniprot (
    orthodb_id INTEGER NOT NULL,
    uniprot_id TEXT NOT NULL
);
.mode csv
.separator \t
.import /tmp/import_data.tab orthodb_to_uniprot

CREATE INDEX orthodb_id_orthodb_id_idx ON orthodb_to_uniprot(orthodb_id);

-- Note: to get orthodb_id in original format use:
-- printf("%d_%d:%06x", orthodb_id>>32, (orthodb_id>>24)&0xFF, orthodb_id&0xFFFFFF)
-- For example:
-- select printf("%d_%d:%06x", orthodb_id>>32, (orthodb_id>>24)&0xFF, orthodb_id&0xFFFFFF) from orthodb_to_uniprot where uniprot_id = "Q92484";


-- Test Request
-- .mode box
-- .headers on
-- SELECT
--     orthodb_id,
--     printf("%d_%d:%06x", orthodb_id>>32, (orthodb_id>>24)&0xFF, orthodb_id&0xFFFFFF) as orig_orthodb_id,
--     uniprot_id
-- FROM orthodb_to_uniprot
-- WHERE uniprot_id = "Q92484";


-- Docker commands
-- docker run -it --rm --user "$(id -u):$(id -g)" --entrypoint bash -v $PWD:/wd --workdir /wd nouchka/sqlite3
-- ./scripts/tabprocessor gene_xrefs odb10v1_gene_xrefs.tab

-- docker exec -it 7462bcdb95c0 bash
-- sqlite3 orthodb.db <./scripts/1_uniprot.sql
