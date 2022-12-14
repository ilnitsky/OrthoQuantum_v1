-- file: odb11v0_gene_xrefs.tab
-- docker run -it --rm --user "$(id -u):$(id -g)" --entrypoint bash -v $PWD:/wd --workdir /wd nouchka/sqlite3
-- ./tabprocessor gene_xrefs_names other/odb11v0_gene_xrefs.tab

-- docker exec -it c58cdca36a1b bash
-- sqlite3 orthodb.db <./scripts/2_gene_names.sql

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

-- В новой версии базы нет NCBIgenename. Забиваем null-ами
-- Старая версия кода в гите

.echo on
.output

DROP TABLE IF EXISTS orthodb_to_name;

CREATE TABLE genes (
    orthodb_id INTEGER NOT NULL,
    uniprot_id TEXT,
    gene_name TEXT
);

INSERT INTO genes
SELECT
    orthodb_id,
    uniprot_id,
    NULL
FROM orthodb_to_uniprot;

DROP TABLE orthodb_to_uniprot;

CREATE INDEX genes_uniprot_id_idx ON genes(uniprot_id);
CREATE INDEX genes_gene_name_idx ON genes(gene_name);
CREATE INDEX genes_orthodb_id_idx ON genes(orthodb_id);
