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

DROP TABLE IF EXISTS orthodb_to_name;

CREATE TABLE orthodb_to_name (
    orthodb_id INTEGER NOT NULL,
    gene_name TEXT NOT NULL
);
.mode csv
.separator \t
.import /tmp/import_data.tab orthodb_to_name

CREATE INDEX orthodb_to_name_orthodb_id_idx ON orthodb_to_name(orthodb_id);

-- Joining the tables

CREATE TABLE genes (
    orthodb_id INTEGER NOT NULL,
    uniprot_id TEXT,
    gene_name TEXT
);

INSERT INTO genes
SELECT
    orthodb_id,
    uniprot_id,
    gene_name
FROM orthodb_to_uniprot
LEFT JOIN orthodb_to_name USING(orthodb_id)
UNION ALL
SELECT
    orthodb_id,
    uniprot_id,
    gene_name
FROM orthodb_to_name
LEFT JOIN orthodb_to_uniprot USING(orthodb_id)
WHERE orthodb_to_uniprot.uniprot_id IS NULL
;

DROP TABLE orthodb_to_uniprot;
DROP TABLE orthodb_to_name;

VACUUM;

CREATE INDEX genes_uniprot_id_idx ON genes(uniprot_id);
CREATE INDEX genes_gene_name_idx ON genes(gene_name);


-- Test Request


-- .mode box
-- .headers on
-- .timer on

-- SELECT
--     orthodb_to_uniprot.orthodb_id,
--     printf(
--         "%d_%d:%06x",
--         orthodb_to_uniprot.orthodb_id>>32,
--         (orthodb_to_uniprot.orthodb_id>>24)&0xFF,
--         orthodb_to_uniprot.orthodb_id&0xFFFFFF
--     ) as orig_orthodb_id,
--     orthodb_to_uniprot.uniprot_id,
--     orthodb_to_name.gene_name
-- FROM orthodb_to_uniprot LEFT JOIN orthodb_to_name
-- ON orthodb_to_uniprot.orthodb_id=orthodb_to_name.orthodb_id
-- WHERE orthodb_to_uniprot.uniprot_id = "Q92484";

