-- file: odb11v0_OG2genes.tab
-- docker run -it --rm --user "$(id -u):$(id -g)" --entrypoint bash -v $PWD:/wd --workdir /wd nouchka/sqlite3
-- ./tabprocessor OG2genes odb11v0_OG2genes.tab

-- docker exec -it c58cdca36a1b bash
-- sqlite3 orthodb.db <./scripts/3_OG.sql


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
    (2759, 'Eukaryota'),
    (2763, 'Rhodophyta'),
    (2836, 'Bacillariophyta'),
    (3041, 'Chlorophyta'),
    (3166, 'Chlorophyceae'),
    (3193, 'Embryophyta'),
    (3646, 'Malpighiales'),
    (3699, 'Brassicales'),
    (3744, 'Rosales'),
    (3745, 'Rosaceae'),
    (4069, 'Solanales'),
    (4085, 'Nicotiana'),
    (4143, 'Lamiales'),
    (4447, 'Liliopsida'),
    (4751, 'Fungi'),
    (4761, 'Chytridiomycota'),
    (4762, 'Oomycota'),
    (4764, 'Saprolegniaceae'),
    (4783, 'Phytophthora'),
    (4827, 'Mucorales'),
    (4890, 'Ascomycota'),
    (4891, 'Saccharomycetes'),
    (4893, 'Saccharomycetaceae'),
    (5042, 'Eurotiales'),
    (5052, 'Aspergillus'),
    (5073, 'Penicillium'),
    (5125, 'Hypocreales'),
    (5129, 'Hypocreaceae'),
    (5139, 'Sordariales'),
    (5178, 'Helotiales'),
    (5204, 'Basidiomycota'),
    (5206, 'Cryptococcus'),
    (5257, 'Ustilaginomycetes'),
    (5303, 'Polyporales'),
    (5317, 'Polyporaceae'),
    (5338, 'Agaricales'),
    (5529, 'Metarhizium'),
    (5583, 'Exophiala'),
    (5658, 'Leishmania'),
    (5690, 'Trypanosoma'),
    (5794, 'Apicomplexa'),
    (5796, 'Coccidia'),
    (5800, 'Eimeria'),
    (5806, 'Cryptosporidium'),
    (5809, 'Sarcocystidae'),
    (5820, 'Plasmodium'),
    (5863, 'Piroplasmida'),
    (5864, 'Babesia'),
    (5878, 'Ciliophora'),
    (6029, 'Microsporidia'),
    (6073, 'Cnidaria'),
    (6101, 'Anthozoa'),
    (6231, 'Nematoda'),
    (6447, 'Mollusca'),
    (6656, 'Arthropoda'),
    (6657, 'Crustacea'),
    (6854, 'Arachnida'),
    (6893, 'Araneae'),
    (6933, 'Acari'),
    (6960, 'Hexapoda'),
    (7041, 'Coleoptera'),
    (7088, 'Lepidoptera'),
    (7147, 'Diptera'),
    (7148, 'Nematocera'),
    (7157, 'Culicidae'),
    (7164, 'Anopheles'),
    (7203, 'Brachycera'),
    (7214, 'Drosophilidae'),
    (7215, 'Drosophila'),
    (7393, 'Glossina'),
    (7399, 'Hymenoptera'),
    (7434, 'Aculeata'),
    (7524, 'Hemiptera'),
    (7742, 'Vertebrata'),
    (7898, 'Actinopterygii'),
    (8457, 'Sauropsida'),
    (8509, 'Squamata'),
    (8782, 'Aves'),
    (8948, 'Falconiformes'),
    (9108, 'Gruiformes'),
    (9126, 'Passeriformes'),
    (9205, 'Pelecaniformes'),
    (9263, 'Metatheria'),
    (9347, 'Eutheria'),
    (9362, 'Eulipotyphla'),
    (9443, 'Primates'),
    (9604, 'Hominidae'),
    (9721, 'Cetacea'),
    (9989, 'Rodentia'),
    (13792, 'Mamiellales'),
    (27994, 'Theileriidae'),
    (28556, 'Pleosporaceae'),
    (28568, 'Trichocomaceae'),
    (28738, 'Cyprinodontiformes'),
    (32523, 'Tetrapoda'),
    (33090, 'Viridiplantae'),
    (33183, 'Onygenales'),
    (33208, 'Metazoa'),
    (33392, 'Holometabola'),
    (33554, 'Carnivora'),
    (33630, 'Alveolata'),
    (33634, 'Stramenopiles'),
    (33682, 'Euglenozoa'),
    (34365, 'Saccharomycodaceae'),
    (34379, 'Pseudeurotiaceae'),
    (34384, 'Arthrodermataceae'),
    (34395, 'Chaetothyriales'),
    (34397, 'Clavicipitaceae'),
    (34735, 'Apoidea'),
    (36668, 'Formicidae'),
    (37572, 'Papilionoidea'),
    (37989, 'Xylariales'),
    (38820, 'Poales'),
    (40674, 'Mammalia'),
    (41084, 'Polyphaga'),
    (41938, 'Malvales'),
    (50557, 'Insecta'),
    (68889, 'Boletales'),
    (71240, 'eudicotyledons'),
    (72025, 'Fabales'),
    (75966, 'Trebouxiophyceae'),
    (91561, 'Artiodactyla'),
    (92860, 'Pleosporales'),
    (93133, 'Mycosphaerellaceae'),
    (110618, 'Nectriaceae'),
    (115784, 'Phaffomycetaceae'),
    (119089, 'Chromadorea'),
    (134362, 'Capnodiales'),
    (142796, 'Eumycetozoa'),
    (147541, 'Dothideomycetes'),
    (147545, 'Eurotiomycetes'),
    (147548, 'Leotiomycetes'),
    (147550, 'Sordariomycetes'),
    (155616, 'Tremellomycetes'),
    (155619, 'Agaricomycetes'),
    (162481, 'Microbotryomycetes'),
    (162484, 'Pucciniomycetes'),
    (231213, 'Sporidiobolales'),
    (299071, 'Ajellomycetaceae'),
    (300275, 'Lachancea'),
    (314145, 'Laurasiatheria'),
    (314146, 'Euarchontoglires'),
    (314147, 'Glires'),
    (314294, 'Cercopithecoidea'),
    (314295, 'Hominoidea'),
    (422676, 'Aconoidasida'),
    (474942, 'Ophiocordycipitaceae'),
    (474943, 'Cordycipitaceae'),
    (490731, 'Kwoniella'),
    (554915, 'Amoebozoa'),
    (766764, 'Debaryomycetaceae'),
    (1028384, 'Glomerellales'),
    (1156497, 'Pichiaceae'),
    (1206795, 'Lophotrochozoa'),
    (1286322, 'Leishmaniinae'),
    (1489911, 'Cichliformes'),
    (1535326, 'Candida'),
    (1549675, 'Galloanserae'),
    (1913637, 'Mucoromycota'),
    (199999999, 'Protista')
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

