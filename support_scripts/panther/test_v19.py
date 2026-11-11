import gzip
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from build_v19 import classification_record,build_classifications,build_relationships,orthologs,canonical
from tree_assets import write_assets,active_species,parse_nhx

ROOT=Path(__file__).resolve().parent
STREAMER=ROOT/'bin/panther_relations'
COLUMNS='Genome TEXT NOT NULL,Genome_2nd_half TEXT NOT NULL,Uniprot TEXT NOT NULL,Gene TEXT NOT NULL,PantherID TEXT NOT NULL,PantherID_2nd_half TEXT NOT NULL,Family TEXT,Subfamily TEXT,col_7 TEXT,col_8 TEXT,col_9 TEXT,col_10 TEXT,col_11 TEXT'

def archive(path,name,rows):
    content=('\n'.join(rows)+'\n').encode()
    with tarfile.open(path,'w:gz') as target:
        info=tarfile.TarInfo(name);info.size=len(content);target.addfile(info,io.BytesIO(content))


class PantherTests(unittest.TestCase):
    def test_classification_compatibility_and_identifiers(self):
        line='HUMAN|HGNC=1|UniProtKB=Q9UL18\tQ9UL18\tAGO1\tPTHR1:SF3\tArgonaute\tAGO1\t\t\t\t\t'
        record=classification_record(line)
        self.assertEqual(len(record),13);self.assertEqual(record[:6],('HUMAN','HGNC=1|UniProtKB=Q9UL18','Q9UL18','AGO1','PTHR1','SF3'))
        self.assertEqual(record[-1],None)
        self.assertEqual(canonical('HUMAN|OtherDB=changed|UniProtKB=Q9UL18')[0],'HUMAN|Q9UL18')
        with self.assertRaises(ValueError):classification_record(line.replace('PTHR1:SF3','WrongID'))

    def test_species_tree_without_semicolon_ignores_unused_metadata_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);metadata=root/'species.tsv';tree=root/'tree.nhx'
            metadata.write_text('organism\treference_proteome_short_name\tcommon_name\ttaxon_id\nHomo sapiens\tHUMAN\thuman\tNCBITaxon:9606\nMus musculus\tMOUSE\tmouse\tNCBITaxon:10090\nOld mouse alias\tOLD\tmouse\tNCBITaxon:10090\n')
            tree.write_text('(HUMAN,MOUSE)[&&NHX:S=Mammalia]\n')
            species=write_assets(metadata,tree,root)
            self.assertEqual(set(species),{'HUMAN','MOUSE'})
            self.assertIn('Homo sapiens',(root/'PANTHER.xml').read_text())
            self.assertIn('HUMAN,9606',(root/'prottree_id_converter.csv').read_text())
            with self.assertRaises(ValueError):parse_nhx('(HUMAN,MOUSE')

    @unittest.skipUnless(STREAMER.exists(),'Compile relationship streamer first')
    def test_real_streamer_build_preserves_source_and_distinguishes_orthologs_paralogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);reference=root/'old.sqlite';classification=root/'new.sqlite'
            with sqlite3.connect(reference) as db:
                db.execute('CREATE TABLE panther('+COLUMNS+')');db.execute('CREATE INDEX pantherid_idx ON panther(PantherID)');db.execute('CREATE INDEX gene_idx ON panther(Gene)')
            before=reference.read_bytes();species={'HUMAN':{},'MOUSE':{}}
            proteins=[('HUMAN','Q9UL18','AGO1','PTHR1:SF1'),('HUMAN','Q92484','SMPDL3A','PTHR3:SF1'),('HUMAN','P05026','ATP1B1','PTHR4:SF1'),('HUMAN','P06748','NPM1','PTHR5:SF1'),('HUMAN','P58004','SESN2','PTHR2:SF1'),('HUMAN','Q9UKV8','AGO2','PTHR1:SF2'),('MOUSE','Q8CJG0','Ago1','PTHR1:SF1')]
            lines=[]
            for genome,up,gene,family in proteins:lines.append('\t'.join([f'{genome}|Gene={gene}|UniProtKB={up}',up,gene,family,'Family',gene,'','','','','']))
            (root/'PTHR19.0_combined').write_text('\n'.join(lines)+'\n')
            with patch('build_v19.shutil.disk_usage',return_value=type('Disk',(),{'free':100*2**30})()):
                stats=build_classifications(classification,root,['PTHR19.0_combined'],reference,species,lambda _:None)
                self.assertEqual(stats['rows'],7);self.assertEqual(reference.read_bytes(),before)
                human='HUMAN|HGNC=updated|UniProtKB=Q9UL18';mouse='MOUSE|Gene=Ago1|UniProtKB=Q8CJG0';ago2='HUMAN|Gene=AGO2|UniProtKB=Q9UKV8'
                archive(root/'AllOrthologs.tar.gz','AllOrthologs',[f'{human}\t{mouse}\tLDO\tMammalia\tPTHR1',f'{ago2}\t{mouse}\tO\tMammalia\tPTHR1'])
                archive(root/'AllParalogs.tar.gz','AllParalogs',[f'{human}\t{ago2}\tP\tMammalia|Root\tPTHR1'])
                result=build_relationships(root/'relations.sqlite',classification,root,STREAMER,lambda _:None)
            self.assertEqual(result['rows'],3);self.assertEqual(result['types'],{'LDO':1,'O':1,'P':1});self.assertEqual(result['extra_genes_not_in_classification'],0)
            with sqlite3.connect(root/'relations.sqlite') as db:
                all_orthologs=orthologs(db,'MOUSE','Q8CJG0');self.assertEqual(len(all_orthologs),2)
                least=orthologs(db,'MOUSE','Q8CJG0',('LDO',));self.assertEqual(len(least),1);self.assertEqual(least[0][:3],('HUMAN','Q9UL18','LDO'))
                self.assertEqual(len(orthologs(db,'HUMAN','Q9UL18',('P',))),1)
            # Corruption must fail even when all tar rows were readable before gzip EOF.
            content=bytearray((root/'AllOrthologs.tar.gz').read_bytes());content[-8]^=1;(root/'AllOrthologs.tar.gz').write_bytes(content)
            seed=root/'seed.tsv';seed.write_text('1\tHUMAN|Q9UL18\n2\tMOUSE|Q8CJG0\n3\tHUMAN|Q9UKV8\n')
            process=subprocess.run([str(STREAMER),str(seed),str(root/'bad.json'),str(root/'AllOrthologs.tar.gz'),str(root/'AllParalogs.tar.gz')],capture_output=True)
            self.assertNotEqual(process.returncode,0)


if __name__=='__main__':unittest.main()
