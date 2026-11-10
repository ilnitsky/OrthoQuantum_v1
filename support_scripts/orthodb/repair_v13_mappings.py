#!/usr/bin/env python3
"""Repair v13 aliases in the unpublished candidate; retain membership data/indexes."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time

GIB=2**30
SAMPLES={'Q9UL18':'AGO1','Q92484':'SMPDL3A','P05026':'ATP1B1','P06748':'NPM1'}
SCHEMA_QUERY="SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC,name"


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)


def verify_samples(db, membership_schema='main', gene_table='genes', aliases=False):
    """Require human aliases, names and Eukaryota membership, not merely any species."""
    found={}
    for accession,symbol in SAMPLES.items():
        if aliases:
            ids=[r[0] for r in db.execute('SELECT orthodb_id FROM u WHERE orthodb_id>=? AND orthodb_id<? AND value=?',(9606<<32,(9606+1)<<32,accession))]
            rows=[]
            for gene in ids:
                names={r[0] for r in db.execute('SELECT value FROM n WHERE orthodb_id=?',(gene,))}
                if symbol not in names:continue
                rows.extend((gene,symbol,cluster,clade) for cluster,clade in db.execute(f'SELECT cluster_id,clade FROM {membership_schema}.orthodb_to_og WHERE orthodb_id=? AND clade=2759',(gene,)))
        else:
            rows=db.execute(f'SELECT g.orthodb_id,g.gene_name,m.cluster_id,m.clade FROM {gene_table} g JOIN {membership_schema}.orthodb_to_og m USING(orthodb_id) WHERE g.uniprot_id=? AND g.gene_name=? AND g.orthodb_id>=? AND g.orthodb_id<? AND m.clade=2759',(accession,symbol,9606<<32,(9606+1)<<32)).fetchall()
        if not rows:raise RuntimeError(f'Missing validated human {accession}/{symbol} Eukaryota mapping')
        found[accession]=rows
    return found


def apply_mapping(candidate,mapping,schema,expected_rows,expected_memberships,progress=lambda stage:None):
    """All changes to main.genes/indexes happen in one rollback-protected transaction."""
    db=sqlite3.connect(candidate,timeout=30,uri=True)
    try:
        last_check=[0.0]
        def disk_guard():
            now=time.monotonic()
            if now-last_check[0]>10:
                last_check[0]=now
                return int(shutil.disk_usage(candidate.parent).free<4*GIB)
            return 0
        db.set_progress_handler(disk_guard,1000000)
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA cache_size=-65536')
        db.execute('PRAGMA temp_store=FILE')
        db.execute('ATTACH DATABASE ? AS repaired',(mapping.resolve().as_uri()+'?mode=ro',))
        if db.execute(SCHEMA_QUERY).fetchall()!=schema:raise RuntimeError('Candidate schema changed before apply')
        db.execute('BEGIN IMMEDIATE')
        progress('Replacing genes inside one atomic transaction')
        indexes=[(name,sql) for kind,name,sql in schema if kind=='index' and name.startswith('genes_')]
        if len(indexes)!=3:raise RuntimeError('Expected three gene indexes')
        for name,_ in indexes:db.execute(f'DROP INDEX "{name}"')
        db.execute('DELETE FROM genes')
        db.execute('INSERT INTO genes SELECT orthodb_id,uniprot_id,gene_name FROM repaired.genes')
        for name,sql in indexes:
            progress('Building '+name)
            db.execute(sql)
        progress('Validating repaired mapping and unchanged memberships')
        if db.execute('SELECT count(*) FROM genes').fetchone()[0]!=expected_rows:raise RuntimeError('Repaired gene row count mismatch')
        if db.execute('SELECT count(*) FROM orthodb_to_og').fetchone()[0]!=expected_memberships:raise RuntimeError('Membership row count changed')
        samples=verify_samples(db)
        if db.execute(SCHEMA_QUERY).fetchall()!=schema:raise RuntimeError('Final schema differs from live reference')
        progress('SQLite quick_check')
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise RuntimeError('Repaired candidate failed quick_check')
        progress('Analyzing gene indexes')
        db.execute('ANALYZE genes')
        db.commit()
        return samples
    except BaseException:
        db.rollback()
        raise
    finally:db.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--archives',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--streamer',type=Path,required=True)
    parser.add_argument('--resume-staged',action='store_true',help='Use a fully prepared, validated mapping file after an interrupted pre-apply run')
    parser.add_argument('--expected-ago-group',type=int,help='Optional independent v13 API check of AGO1 group at level 2759')
    args=parser.parse_args()
    source,output=args.source.resolve(),args.output.resolve()
    candidate=Path(str(output)+'.building')
    mapping=Path(str(output)+'.mapping.sqlite')
    report_path=Path(str(output)+'.repair.json')
    if source in (output,candidate,mapping) or output.exists() or not candidate.is_file():raise RuntimeError('Requires a separate existing unpublished candidate and no final output')
    temp_dir=Path(str(output)+'.repair-tmp')
    temp_dir.mkdir(mode=0o700,exist_ok=True)
    os.environ['SQLITE_TMPDIR']=str(temp_dir)
    lock=open(str(output)+'.repair.lock','a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    build_path=Path(str(output)+'.build.json')
    build=json.loads(build_path.read_text())
    if build.get('source_schema')!=str(source):raise RuntimeError('Reference path differs from original build')
    if build.get('status')!='failed' or build.get('error')!='Human AGO1 UniProt lookup returned no Eukaryota membership':raise RuntimeError('Repair is limited to the audited mapping-validation failure')
    if build['release']!='odb13v0' or any(build['stages'].get(stage,{}).get('status')!='complete' for stage in ('genes','memberships')):raise RuntimeError('Initial data import must be complete')
    status=json.loads((args.archives/'download-status.json').read_text())
    name='odb13v0_gene_xrefs.tab.gz';archive=args.archives/name;info=status['files'][name]
    if status.get('release')!='odb13v0' or info['status']!='verified' or info['md5']!=info['expected_md5'] or build['input_md5'].get(name)!=info['md5'] or archive.stat().st_size!=info['bytes']:raise RuntimeError('Cross-reference input does not match verified original archive')
    if shutil.disk_usage(output.parent).free<24*GIB:raise RuntimeError('Require 24 GiB free before staging mappings')
    with readonly(source) as ref:schema=ref.execute(SCHEMA_QUERY).fetchall()
    with readonly(candidate) as db:
        if db.execute(SCHEMA_QUERY).fetchall()!=schema:raise RuntimeError('Candidate schema differs from reference')
    identity={'size':candidate.stat().st_size,'mtime_ns':candidate.stat().st_mtime_ns,'xref_md5':info['md5']}
    previous=json.loads(report_path.read_text()) if report_path.exists() else None
    if args.resume_staged:
        if previous and previous.get('mapping_file'):
            mapping=Path(previous['mapping_file']).resolve()
            if mapping.parent!=output.parent or mapping.name!=output.name+'.symbols.sqlite':raise RuntimeError('Invalid prepared symbols path')
        if not previous or previous.get('phase')!='mapping_ready' or previous.get('identity')!=identity or not mapping.is_file():raise RuntimeError('Resume requires a fully prepared mapping and unchanged candidate/input')
        report=previous
    else:
        if mapping.exists() or report_path.exists():raise RuntimeError('Mapping/report already exists; refusing to overwrite a previous repair')
        report={'status':'repairing','phase':'starting','started_unix':int(time.time()),'identity':identity,'source':str(source),'output':str(output),'stages':{}}

    def save():
        temp=Path(str(report_path)+'.tmp');temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(report_path)
    def progress(stage):
        report['message']=stage;report['updated_unix']=int(time.time());save();print(stage,flush=True)
    started=time.monotonic();save()
    try:
        if not args.resume_staged:
            # Scratch only: the original candidate and live database stay read-only.
            db=sqlite3.connect(mapping,uri=True)
            try:
                db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-65536; PRAGMA temp_store=FILE; CREATE TABLE raw_u(orthodb_id INTEGER,value TEXT); CREATE TABLE raw_n(orthodb_id INTEGER,value TEXT); CREATE TABLE fallback_n(orthodb_id INTEGER,value TEXT);')
                db.execute('ATTACH DATABASE ? AS baseline',(candidate.as_uri()+'?mode=ro',))
                progress('Preserving initial UniProt mappings and fallback names')
                db.execute('INSERT INTO raw_u SELECT orthodb_id,uniprot_id FROM baseline.genes WHERE uniprot_id IS NOT NULL')
                db.execute('INSERT INTO fallback_n SELECT orthodb_id,gene_name FROM baseline.genes WHERE gene_name IS NOT NULL')
                db.commit()
                progress('Streaming UniProt and NCBIgenename cross-references')
                stats_path=Path(str(output)+'.xrefs.json')
                env=dict(os.environ,ORTHODB_STREAM_STATS=str(stats_path))
                process=subprocess.Popen([str(args.streamer.resolve()),'xrefs',str(archive.resolve()),'2759'],stdout=subprocess.PIPE,env=env)
                count=0;batch_u=[];batch_n=[]
                try:
                    def flush():
                        if batch_u:db.executemany('INSERT INTO raw_u VALUES (?,?)',batch_u);batch_u.clear()
                        if batch_n:db.executemany('INSERT INTO raw_n VALUES (?,?)',batch_n);batch_n.clear()
                        db.commit()
                    for line in process.stdout:
                        fields=line.decode().rstrip('\n').split('\t')
                        if len(fields)!=3 or fields[1] not in ('U','N'):raise RuntimeError('Malformed xref streamer record')
                        gene=int(fields[0])
                        (batch_u if fields[1]=='U' else batch_n).append((gene,fields[2]));count+=1
                        if gene>>32==9606 and fields[2] in {*SAMPLES,*SAMPLES.values()}:
                            hits=report.setdefault('human_mapping_hits',{})
                            hits[fields[2]]=hits.get(fields[2],0)+1
                        if count%100000==0:
                            flush()
                            if shutil.disk_usage(output.parent).free<8*GIB:raise RuntimeError('Free disk space below staging reserve')
                        if count%5000000==0:
                            report['stages']['xrefs']={'rows':count,'status':'loading'};progress(f'Cross-references: {count:,} imported')
                    flush()
                    if process.wait()!=0:raise RuntimeError('Cross-reference streamer failed')
                finally:
                    process.stdout.close()
                    if process.poll() is None:process.terminate();process.wait()
                stats=json.loads(stats_path.read_text())
                if stats['compatible_records']!=count:raise RuntimeError('Cross-reference row count mismatch')
                report['stages']['xrefs']={**stats,'rows':count,'status':'complete'};save()
                progress('Deduplicating UniProt aliases')
                db.execute('CREATE TABLE u(orthodb_id INTEGER,value TEXT,PRIMARY KEY(orthodb_id,value)) WITHOUT ROWID')
                db.execute('INSERT OR IGNORE INTO u SELECT orthodb_id,value FROM raw_u ORDER BY orthodb_id,value');db.commit()
                progress('Deduplicating authoritative gene-name aliases')
                db.execute('CREATE TABLE n(orthodb_id INTEGER,value TEXT,PRIMARY KEY(orthodb_id,value)) WITHOUT ROWID')
                db.execute('INSERT OR IGNORE INTO n SELECT orthodb_id,value FROM raw_n ORDER BY orthodb_id,value');db.commit()
                db.execute('CREATE INDEX raw_n_id ON raw_n(orthodb_id)')
                db.execute('INSERT OR IGNORE INTO n SELECT f.orthodb_id,f.value FROM fallback_n f WHERE NOT EXISTS(SELECT 1 FROM raw_n x WHERE x.orthodb_id=f.orthodb_id) ORDER BY f.orthodb_id,f.value');db.commit()
                progress('Checking human canonical accessions and gene symbols against preserved memberships')
                samples=verify_samples(db,'baseline',aliases=True)
                if args.expected_ago_group and not any(row[2]==args.expected_ago_group for row in samples['Q9UL18']):raise RuntimeError('AGO1 group differs from independent v13 API check')
                report['sample_queries']=samples;save()
                progress('Building the replacement gene table with the original schema')
                db.execute(next(sql for kind,name,sql in schema if kind=='table' and name=='genes'))
                count1=db.execute('INSERT INTO genes SELECT u.orthodb_id,u.value,n.value FROM u LEFT JOIN n USING(orthodb_id)').rowcount
                count2=db.execute('INSERT INTO genes SELECT n.orthodb_id,NULL,n.value FROM n WHERE NOT EXISTS(SELECT 1 FROM u WHERE u.orthodb_id=n.orthodb_id)').rowcount
                db.commit();report['gene_rows']=count1+count2
                # Reclaim staging space before the rollback-protected main-DB repair.
                progress('Compacting the prepared mapping database')
                for table in ('raw_u','raw_n','fallback_n','u','n'):db.execute(f'DROP TABLE {table}')
                db.commit();db.execute('DETACH DATABASE baseline');db.execute('VACUUM');db.close();db=None
            finally:
                if db is not None:db.close()
            report['phase']='mapping_ready';progress('Mapping file ready; candidate unchanged')
        if {'size':candidate.stat().st_size,'mtime_ns':candidate.stat().st_mtime_ns,'xref_md5':info['md5']}!=report['identity']:raise RuntimeError('Candidate changed during read-only staging')
        reserve=max(16*GIB,mapping.stat().st_size*2+6*GIB)
        if shutil.disk_usage(output.parent).free<reserve:raise RuntimeError('Insufficient rollback/index reserve; mapping is ready for --resume-staged')
        report['phase']='applying';progress('Starting atomic gene-mapping repair')
        samples=apply_mapping(candidate,mapping,schema,report['gene_rows'],build['stages']['memberships']['rows'],progress)
        report['phase']='validated';report['sample_queries']=samples;save()
        with candidate.open('rb') as completed:os.fsync(completed.fileno())
        os.link(candidate,output);candidate.unlink()
        report.update(status='complete',phase='published',seconds=round(time.monotonic()-started),bytes=output.stat().st_size);progress('Published validated NEW v13 candidate; live database unchanged')
        build['stages']['genes_direct_initial']=build['stages']['genes']
        build['stages']['genes']={'rows':report['gene_rows'],'status':'complete','source':'genes summary plus dedicated gene_xrefs; authoritative gene names, fallback summary names'}
        build.update(status='complete',mapping_repair=str(report_path),sample_queries=samples,quick_check='ok',schema_matches_reference=True,bytes=output.stat().st_size)
        build.pop('error',None)
        temp=Path(str(build_path)+'.tmp');temp.write_text(json.dumps(build,indent=2)+'\n');temp.replace(build_path)
    except BaseException as error:
        report.update(status='failed',error=str(error));save();raise
    finally:lock.close()


if __name__=='__main__':main()
