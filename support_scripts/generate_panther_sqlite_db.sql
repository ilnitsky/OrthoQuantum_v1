CREATE TABLE panther_import (
    Genome TEXT NOT NULL,
    Uniprot TEXT NOT NULL,
    Gene TEXT NOT NULL,
    PantherID TEXT NOT NULL,
    Family TEXT NOT NULL,
    Subfamily TEXT NOT NULL,
    col_7 TEXT NOT NULL,
    col_8 TEXT NOT NULL,
    col_9 TEXT NOT NULL,
    col_10 TEXT NOT NULL,
    col_11 TEXT NOT NULL
);

CREATE TABLE panther (
    Genome TEXT NOT NULL,
    Genome_2nd_half TEXT NOT NULL,
    Uniprot TEXT NOT NULL,
    Gene TEXT NOT NULL,
    PantherID TEXT NOT NULL,
    PantherID_2nd_half TEXT NOT NULL,
    Family TEXT,
    Subfamily TEXT,
    col_7 TEXT,
    col_8 TEXT,
    col_9 TEXT,
    col_10 TEXT,
    col_11 TEXT
);

.mode csv
.separator "\t"
.import PTHRfull.txt panther_import

INSERT INTO panther
SELECT SUBSTR(Genome, 0, INSTR(Genome,"|")), SUBSTR(Genome, INSTR(Genome,"|")+1), Uniprot, Gene, SUBSTR(PantherID, 0, INSTR(PantherID,":")), SUBSTR(PantherID, INSTR(PantherID,":")+1), Family, Subfamily, col_7, col_8, col_9, col_10, col_11
FROM panther_import;

DROP TABLE panther_import;
UPDATE panther SET Family=NULL WHERE TRIM(Family)="";
UPDATE panther SET Subfamily=NULL WHERE TRIM(Subfamily)="";
UPDATE panther SET col_7=NULL WHERE TRIM(col_7)="";
UPDATE panther SET col_8=NULL WHERE TRIM(col_8)="";
UPDATE panther SET col_9=NULL WHERE TRIM(col_9)="";
UPDATE panther SET col_10=NULL WHERE TRIM(col_10)="";
UPDATE panther SET col_11=NULL WHERE TRIM(col_11)="";

CREATE INDEX pantherid_idx ON panther (PantherID);
CREATE INDEX gene_idx ON panther (Gene);

VACUUM;
