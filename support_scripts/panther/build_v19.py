#!/usr/bin/env python3
"""Download pinned PANTHER v19 data and build an isolated, validated DB bundle."""
import argparse
import concurrent.futures
import fcntl
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from tree_assets import species_table,active_species,write_assets

CLASS_URL='https://data.pantherdb.org/ftp/sequence_classifications/19.0/PANTHER_Sequence_Classification_files/'
REL_URL='https://data.pantherdb.org/ftp/ortholog/19.0/'
GLOBAL_URL='https://data.pantherdb.org/PANTHER19.0/globals/'
GIB=2**30
HUMAN={'Q9UL18':'AGO1','Q92484':'SMPDL3A','P05026':'ATP1B1','P06748':'NPM1'}


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(4*1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


class Catalog(HTMLParser):
    def __init__(self):super().__init__();self.names=set()
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            if re.fullmatch(r'PTHR19\.0_[A-Za-z0-9_]+',href):self.names.add(href)


def download(url,path,proxy):
    common=['curl','--fail','--silent','--show-error','--location','--retry','3','--connect-timeout','20']
    if proxy:common+=['--proxy',proxy]
    header=subprocess.run(common+['--head','--max-time','60',url],capture_output=True,check=True,text=True).stdout
    headers={}
    for line in header.splitlines():
        if line.startswith('HTTP/'):headers={}
        elif ':' in line:
            key,value=line.split(':',1);headers[key.lower()]=value.strip()
    size=int(headers['content-length']) if headers.get('content-length','').isdigit() else None
    if size is not None and size>2*GIB:raise RuntimeError('Unexpectedly large download: '+url)
    identity={k:headers.get(k) for k in ('etag','last-modified','content-length')}
    metadata=Path(str(path)+'.source.json')
    if path.exists() and metadata.exists():
        old=json.loads(metadata.read_text())
        if old.get('headers')==identity and (size is None or path.stat().st_size==size) and sha256(path)==old.get('sha256'):return old
        raise RuntimeError('Previously downloaded source changed; refusing to mix releases: '+path.name)
    partial=Path(str(path)+'.part')
    partial_meta=Path(str(partial)+'.json')
    if partial.exists() and partial_meta.exists() and json.loads(partial_meta.read_text())!=identity:
        raise RuntimeError('Partial file belongs to changed source: '+path.name)
    partial_meta.write_text(json.dumps(identity))
    if not (partial.exists() and size is not None and partial.stat().st_size==size):
        subprocess.run(common+['--max-time','7200','--max-filesize',str(2*GIB),'--continue-at','-','--output',str(partial),url],check=True)
    if size is not None and partial.stat().st_size!=size:raise RuntimeError('Incomplete download: '+path.name)
    result={'url':url,'headers':identity,'bytes':partial.stat().st_size,'sha256':sha256(partial)}
    partial.replace(path);metadata.write_text(json.dumps(result,indent=2)+'\n')
    return result


def canonical(identifier):
    parts=identifier.split('|');genome=parts[0]
    uniprot=next((part.split('=',1)[1] for part in parts[1:] if part.startswith('UniProtKB=')),None)
    if not genome or not uniprot:raise ValueError('Invalid PANTHER gene identifier: '+identifier)
    return genome+'|'+uniprot,genome,uniprot


def classification_record(line):
    fields=line.rstrip('\r\n').split('\t')
    if len(fields)!=11:raise ValueError(f'Classification requires 11 fields, got {len(fields)}')
    identifier,uniprot,gene,family,*values=fields
    _,genome,mapped=canonical(identifier)
    if mapped!=uniprot:raise ValueError('UniProt columns disagree for '+identifier)
    if not re.fullmatch(r'PTHR\d+(?::SF\d+)?',family):raise ValueError('Invalid family/subfamily ID: '+family)
    family,_,subfamily=family.partition(':')
    return (genome,identifier.partition('|')[2],uniprot,gene,family,subfamily,*[v if v.strip() else None for v in values])


def connect(path):
    db=sqlite3.connect(path)
    db.executescript('PRAGMA journal_mode=OFF;PRAGMA synchronous=OFF;PRAGMA temp_store=FILE;PRAGMA cache_size=-32768;')
    last=[0.0]
    def guard():
        now=time.monotonic()
        if now-last[0]>10:
            last[0]=now
            return int(shutil.disk_usage(path.parent).free<8*GIB)
        return 0
    db.set_progress_handler(guard,1000000)
    return db


def build_classifications(db_path,downloads,names,reference,species,progress):
    with sqlite3.connect(reference.resolve().as_uri()+'?mode=ro',uri=True) as ref:
        sql=ref.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='panther'").fetchone()[0]
        columns=ref.execute('PRAGMA table_info(panther)').fetchall()
        legacy_indexes=ref.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchall()
    if len(columns)!=13:raise RuntimeError('Unexpected legacy PANTHER schema')
    db=connect(db_path);count=0;genomes=set()
    try:
        db.execute(sql)
        for name in names:
            batch=[];file_count=0
            with (downloads/name).open(encoding='utf-8') as source:
                for line in source:
                    if not line.strip():continue
                    row=classification_record(line)
                    if row[0] not in species:raise RuntimeError('Unknown classification genome: '+row[0])
                    genomes.add(row[0]);batch.append(row);count+=1;file_count+=1
                    if len(batch)==10000:db.executemany('INSERT INTO panther VALUES('+','.join('?'*13)+')',batch);db.commit();batch=[]
            if batch:db.executemany('INSERT INTO panther VALUES('+','.join('?'*13)+')',batch);db.commit()
            if not file_count:raise RuntimeError('Empty classification file: '+name)
            progress(f'Classifications: {count:,} records; loaded {name}')
        if genomes!=set(species):raise RuntimeError('Classification/species coverage mismatch: '+str(set(species)-genomes))
        if db.execute('PRAGMA table_info(panther)').fetchall()!=columns:raise RuntimeError('Legacy panther table schema changed')
        for name,sql in legacy_indexes:progress('Building '+name);db.execute(sql);db.commit()
        for name,sql in [
            ('panther_uniprot_idx','CREATE INDEX panther_uniprot_idx ON panther(Uniprot)'),
            ('panther_genome_uniprot_idx','CREATE INDEX panther_genome_uniprot_idx ON panther(Genome,Uniprot)')]:progress('Building '+name);db.execute(sql);db.commit()
        samples={}
        for acc,symbol in HUMAN.items():
            rows=db.execute('SELECT Genome,Gene,PantherID,PantherID_2nd_half,Subfamily FROM panther WHERE Genome=? AND Uniprot=?',('HUMAN',acc)).fetchall()
            if not rows or not any(row[1]==symbol for row in rows):raise RuntimeError('Missing v19 human mapping '+acc+'/'+symbol)
            samples[acc]=rows
        if not db.execute("SELECT 1 FROM panther WHERE Genome='HUMAN' AND Gene='SESN2'").fetchone():raise RuntimeError('SESN2 example unavailable')
        db.execute('ANALYZE');db.commit()
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise RuntimeError('Classification database failed quick_check')
        return {'rows':count,'species':len(genomes),'human_samples':samples}
    finally:db.close()


def build_relationships(path,classification,downloads,streamer,progress,species=None):
    db=connect(path);count=0
    try:
        db.executescript('''CREATE TABLE genes(gene_id INTEGER PRIMARY KEY,canonical_key TEXT NOT NULL UNIQUE,genome TEXT NOT NULL,uniprot TEXT NOT NULL,original_id TEXT NOT NULL);
        CREATE TABLE relationships(gene_a INTEGER NOT NULL,gene_b INTEGER NOT NULL,relation TEXT NOT NULL CHECK(relation IN ('LDO','O','P')),ancestor_id INTEGER NOT NULL,family_id INTEGER NOT NULL);
        CREATE TABLE ancestors(ancestor_id INTEGER PRIMARY KEY,name TEXT NOT NULL);
        CREATE TABLE families(family_id INTEGER PRIMARY KEY,panther_id TEXT NOT NULL);''')
        db.execute('ATTACH DATABASE ? AS class',(classification.resolve().as_uri()+'?mode=ro',))
        db.execute("INSERT OR IGNORE INTO genes(canonical_key,genome,uniprot,original_id) SELECT Genome||'|'||Uniprot,Genome,Uniprot,Genome||'|'||Genome_2nd_half FROM class.panther");db.commit()
        seed=path.with_suffix('.gene_keys.tsv')
        with seed.open('w') as target:
            for row in db.execute('SELECT gene_id,canonical_key FROM genes ORDER BY gene_id'):target.write(f'{row[0]}\t{row[1]}\n')
        metadata=path.with_suffix('.stream.json')
        command=[str(streamer.resolve()),str(seed),str(metadata),str(downloads/'AllOrthologs.tar.gz'),str(downloads/'AllParalogs.tar.gz')]
        progress('Streaming normalized v19 ortholog/paralog relationships')
        process=subprocess.Popen(command,stdout=subprocess.PIPE);batch=[];extra=[]
        try:
            for line in process.stdout:
                fields=line.decode().rstrip('\n').split('\t')
                if fields[0]=='G' and len(fields)==5:
                    _,number,genome,uniprot,original=fields;extra.append((int(number),genome+'|'+uniprot,genome,uniprot,original))
                elif fields[0]=='R' and len(fields)==6:
                    batch.append((int(fields[1]),int(fields[2]),fields[3],int(fields[4]),int(fields[5])));count+=1
                else:raise RuntimeError('Invalid relationship streamer output')
                if len(batch)>=50000:
                    if extra:db.executemany('INSERT INTO genes VALUES(?,?,?,?,?)',extra);extra.clear()
                    db.executemany('INSERT INTO relationships VALUES(?,?,?,?,?)',batch);db.commit();batch.clear()
                if count and count%2000000==0:progress(f'Relationships: {count:,} rows')
            if extra:db.executemany('INSERT INTO genes VALUES(?,?,?,?,?)',extra)
            if batch:db.executemany('INSERT INTO relationships VALUES(?,?,?,?,?)',batch)
            db.commit()
            if process.wait()!=0:raise RuntimeError('Relationship parser failed')
        finally:
            process.stdout.close()
            if process.poll() is None:process.terminate();process.wait()
        stats=json.loads(metadata.read_text())
        if count!=stats['rows'] or not all(stats['types'].get(k) for k in ('LDO','O','P')):raise RuntimeError('Missing relationship types or inconsistent counts')
        db.executemany('INSERT INTO ancestors VALUES(?,?)',[(value,key) for key,value in stats['ancestors'].items()])
        db.executemany('INSERT INTO families VALUES(?,?)',[(value,key) for key,value in stats['families'].items()]);db.commit()
        for name,sql in [
            ('relationships_a_idx','CREATE INDEX relationships_a_idx ON relationships(gene_a,relation,gene_b)'),
            ('relationships_b_idx','CREATE INDEX relationships_b_idx ON relationships(gene_b,relation,gene_a)'),
            ('genes_genome_uniprot_idx','CREATE INDEX genes_genome_uniprot_idx ON genes(genome,uniprot)')]:progress('Building '+name);db.execute(sql);db.commit()
        for column in ('gene_a','gene_b'):
            if db.execute(f'SELECT 1 FROM (SELECT DISTINCT {column} AS gene_id FROM relationships) r LEFT JOIN genes g USING(gene_id) WHERE g.gene_id IS NULL LIMIT 1').fetchone():raise RuntimeError('Unresolved gene relationship endpoint')
        for table,column,key in [('ancestors','ancestor_id','ancestor_id'),('families','family_id','family_id')]:
            if db.execute(f'SELECT 1 FROM (SELECT DISTINCT {column} FROM relationships) r LEFT JOIN {table} d ON r.{column}=d.{key} WHERE d.{key} IS NULL LIMIT 1').fetchone():raise RuntimeError('Unresolved relationship dictionary')
        if db.execute('SELECT count(*) FROM genes').fetchone()[0]!=stats['genes']:raise RuntimeError('Normalized gene dictionary count mismatch')
        if species is not None:
            genomes={row[0] for row in db.execute('SELECT DISTINCT genome FROM genes')}
            if not genomes.issubset(species):raise RuntimeError('Relationship genomes are not in the versioned tree: '+str(genomes-set(species)))
        if db.execute('SELECT count(*) FROM relationships').fetchone()[0]!=count:raise RuntimeError('Relationship count mismatch')
        sample=orthologs(db,'HUMAN','Q9UL18')
        if not sample or not any(row[0]=='MOUSE' for row in sample):raise RuntimeError('No human AGO1-to-mouse ortholog evidence')
        progress('Checking normalized relationships database')
        db.execute('ANALYZE main');db.commit()
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise RuntimeError('Relationship database failed quick_check')
        return {'rows':count,'types':stats['types'],'source_archives':stats['archives'],'extra_genes_not_in_classification':stats['extra_genes'],'human_ago1_example':sample[:20]}
    finally:db.close()


def orthologs(db,genome,uniprot,types=('LDO','O')):
    source=db.execute('SELECT gene_id FROM genes WHERE genome=? AND uniprot=?',(genome,uniprot)).fetchone()
    if not source:return []
    marks=','.join('?' for _ in types)
    return db.execute(f'''SELECT DISTINCT g.genome,g.uniprot,r.relation,a.name,f.panther_id FROM
      (SELECT gene_b AS target,relation,ancestor_id,family_id FROM relationships WHERE gene_a=? AND relation IN ({marks})
       UNION ALL SELECT gene_a,relation,ancestor_id,family_id FROM relationships WHERE gene_b=? AND relation IN ({marks})) r
      JOIN genes g ON g.gene_id=r.target JOIN ancestors a USING(ancestor_id) JOIN families f USING(family_id)''',[source[0],*types,source[0],*types]).fetchall()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New versioned bundle directory, never the live DB path')
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--streamer',type=Path,required=True)
    parser.add_argument('--proxy',default='socks5h://127.0.0.1:10808')
    parser.add_argument('--wait-for-orthodb',type=Path)
    args=parser.parse_args();output=args.output.resolve();downloads=args.downloads.resolve();staging=Path(str(output)+'.building')
    if output.exists() or staging.exists():raise RuntimeError('Output/staging exists; refusing overwrite')
    if output==args.reference.resolve() or output.parent==args.reference.resolve():raise RuntimeError('Output must be a new bundle directory')
    downloads.mkdir(parents=True,exist_ok=True)
    lock=open(downloads/'build.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    report_path=Path(str(output)+'.build.json')
    report={'release':'PANTHER19.0','status':'building','phase':'download','started_unix':int(time.time()),'files':{},'output':str(output)}
    def progress(message):
        report['message']=message;report['updated_unix']=int(time.time())
        temp=Path(str(report_path)+'.tmp');temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(report_path);print(message,flush=True)
    try:
        if shutil.disk_usage(output.parent).free<32*GIB:raise RuntimeError('Require 32 GiB free before PANTHER downloads; preserve OrthoDB repair reserve')
        globals_=[('species_list.tsv',GLOBAL_URL+'species_list.tsv'),('species_pthr19_annot.nhx',GLOBAL_URL+'species_pthr19_annot.nhx'),('ortholog_README.txt',REL_URL+'README'),('classification_index.html',CLASS_URL)]
        for name,url in globals_:report['files'][name]=download(url,downloads/name,args.proxy)
        catalog=Catalog();catalog.feed((downloads/'classification_index.html').read_text());names=sorted(catalog.names)
        species=active_species(downloads/'species_list.tsv',downloads/'species_pthr19_annot.nhx')
        report['unused_species_metadata_codes']=sorted(set(species_table(downloads/'species_list.tsv'))-set(species))
        if not names:raise RuntimeError('Empty v19 classification catalog')
        # The green_algae file contains BOTH CHLRE and KLENI: 143 files, 144 species.
        # Validate genome coverage from the rows, not by assuming one file/species.
        report['classification_files']=len(names)
        tasks=[(name,CLASS_URL+name) for name in names]+[(name,REL_URL+name) for name in ('AllOrthologs.tar.gz','AllParalogs.tar.gz')]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures={pool.submit(download,url,downloads/name,args.proxy):name for name,url in tasks}
            for future in concurrent.futures.as_completed(futures):
                name=futures[future];report['files'][name]=future.result();progress(f'Downloaded {len(report["files"])}/{len(tasks)+len(globals_)} files: {name}')
        report['phase']='waiting'
        if args.wait_for_orthodb:
            while args.wait_for_orthodb.exists():
                other=json.loads(args.wait_for_orthodb.read_text())
                if other.get('status')!='repairing':break
                progress('Downloads ready; waiting for OrthoDB mapping repair before heavy SQLite writes')
                time.sleep(30)
        if shutil.disk_usage(output.parent).free<24*GIB:raise RuntimeError('Require 24 GiB free before building versioned PANTHER databases')
        staging.mkdir();temp_dir=staging/'tmp';temp_dir.mkdir();os.environ['SQLITE_TMPDIR']=str(temp_dir)
        report['phase']='species_assets';progress('Building matching v19 species/tree assets')
        species=write_assets(downloads/'species_list.tsv',downloads/'species_pthr19_annot.nhx',staging)
        report['phase']='classification';progress('Building legacy-compatible PANTHER classification database')
        report['classification']=build_classifications(staging/'panther.sqlite',downloads,names,args.reference,species,progress)
        report['phase']='relationships';report['relationships']=build_relationships(staging/'relationships.sqlite',staging/'panther.sqlite',downloads,args.streamer,progress,species)
        shutil.copyfile(downloads/'species_list.tsv',staging/'species_list.tsv')
        shutil.copyfile(downloads/'species_pthr19_annot.nhx',staging/'species_pthr19_annot.nhx')
        report.update(status='complete',phase='validated',species=len(species),seconds=int(time.time())-report['started_unix'])
        (staging/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
        for name in ('panther.sqlite','relationships.sqlite','manifest.json'):
            with (staging/name).open('rb') as completed:os.fsync(completed.fileno())
        if output.exists():raise RuntimeError('Output appeared; refusing replacement')
        staging.rename(output);progress('Published validated PANTHER v19 bundle; live DB unchanged')
    except BaseException as error:
        report.update(status='failed',error=str(error));progress('PANTHER build stopped: '+str(error));raise
    finally:lock.close()


if __name__=='__main__':main()
