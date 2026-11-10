#!/usr/bin/env python3
"""Recover v13 symbols via NCBI Gene IDs, reusing the completed UniProt staging."""
import argparse
import concurrent.futures
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from repair_v13_mappings import readonly,SCHEMA_QUERY,verify_samples,apply_mapping,GIB

URL='https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_info.gz'


def fetch_gene_info(path,proxy):
    """Pin the daily source by HTTP metadata + local SHA256; reject changed resumes."""
    common=['curl','--fail','--silent','--show-error','--location','--retry','4','--connect-timeout','20']
    if proxy:common+=['--proxy',proxy]
    headers={}
    for line in subprocess.check_output(common+['--head','--max-time','60',URL],text=True).splitlines():
        if line.startswith('HTTP/'):headers={}
        elif ':' in line:
            k,v=line.split(':',1);headers[k.lower()]=v.strip()
    identity={k:headers.get(k) for k in ('last-modified','etag','content-length')}
    size=int(headers['content-length'])
    if size>4*GIB:raise RuntimeError('Unexpected NCBI download size')
    meta=Path(str(path)+'.source.json');partial=Path(str(path)+'.part')
    if meta.exists():
        previous=json.loads(meta.read_text())
        if previous['headers']!=identity:raise RuntimeError('NCBI daily source changed: retain old input or use a new source directory')
    else:meta.write_text(json.dumps({'url':URL,'headers':identity},indent=2)+'\n')
    if not path.exists():
        if not (partial.exists() and partial.stat().st_size==size):
            subprocess.run(common+['--max-time','14400','--max-filesize',str(4*GIB),'--continue-at','-','--output',str(partial),URL],check=True)
        if partial.stat().st_size!=size:raise RuntimeError('NCBI download length mismatch')
        partial.replace(path)
    if path.stat().st_size!=size:raise RuntimeError('NCBI source length mismatch')
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(4*1024*1024),b''):digest.update(block)
    value=digest.hexdigest()
    if meta.exists() and json.loads(meta.read_text()).get('sha256',value)!=value:raise RuntimeError('NCBI source checksum changed')
    result={'url':URL,'headers':identity,'bytes':size,'sha256':value,'checksum_origin':'locally calculated; not a publisher checksum'}
    meta.write_text(json.dumps(result,indent=2)+'\n');return result


def load_gene_info(db,path,progress=lambda _:None):
    """Load explicit NCBI symbols and source aliases; never derive names from descriptions."""
    db.execute('DROP TABLE IF EXISTS gene_info')
    db.execute('CREATE TABLE gene_info(gene_id INTEGER PRIMARY KEY,taxid INTEGER,symbol TEXT,authority_symbol TEXT,synonyms TEXT)')
    rows=0;batch=[]
    with gzip.open(path,'rt',encoding='utf-8') as source:
        for line in source:
            if line.startswith('#'):continue
            fields=line.rstrip('\r\n').split('\t')
            if len(fields)!=16:raise RuntimeError('Expected the documented 16-column NCBI gene_info format')
            taxid,gene=int(fields[0]),int(fields[1])
            if taxid<=0 or gene<=0:raise RuntimeError('Invalid NCBI gene/taxonomy ID')
            symbol=fields[2] if fields[2]!='-' else None
            authority=fields[10] if fields[10]!='-' else None
            synonyms=fields[4] if fields[4]!='-' else None
            batch.append((gene,taxid,symbol,authority,synonyms));rows+=1
            if len(batch)==100000:
                db.executemany('INSERT INTO gene_info VALUES (?,?,?,?,?)',batch);db.commit();batch.clear()
            if rows%2000000==0:progress(f'NCBI gene_info: {rows:,} records')
        if batch:db.executemany('INSERT INTO gene_info VALUES (?,?,?,?,?)',batch);db.commit()
    return rows


def match_symbols(db,progress=lambda _:None):
    """Require exact GeneID AND species. Keep symbols normalized in n."""
    counts={'matched_gene_links':0,'taxid_mismatches':0,'unresolved_gene_links':0,'symbol_records':0}
    # Separate read cursor and batched inserts; input tables are never modified here.
    rows=db.execute('SELECT i.orthodb_id,g.taxid,g.symbol,g.authority_symbol,g.synonyms FROM i LEFT JOIN gene_info g ON g.gene_id=i.gene_id ORDER BY i.gene_id,i.orthodb_id')
    batch=[]
    for packed,taxid,symbol,authority,synonyms in rows:
        if taxid is None:counts['unresolved_gene_links']+=1;continue
        if packed>>32!=taxid:counts['taxid_mismatches']+=1;continue
        counts['matched_gene_links']+=1
        names={v.strip() for v in [symbol,authority] if v and v.strip() and v.strip()!='-'}
        for name in names:batch.append((packed,name))
        if len(batch)>=100000:
            before=db.total_changes;db.executemany('INSERT OR IGNORE INTO n VALUES (?,?)',batch);counts['symbol_records']+=db.total_changes-before;batch.clear();db.commit()
            progress(f"Gene symbols: {counts['matched_gene_links']:,} exact-species links matched")
    if batch:
        before=db.total_changes;db.executemany('INSERT OR IGNORE INTO n VALUES (?,?)',batch);counts['symbol_records']+=db.total_changes-before
    db.commit();return counts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('source','archives','output','streamer','sources'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--proxy',default='');p.add_argument('--expected-ago-group',type=int,default=8905661)
    args=p.parse_args();output=args.output.resolve();candidate=Path(str(output)+'.building');mapping=Path(str(output)+'.mapping.sqlite')
    report_path=Path(str(output)+'.repair.json');build_path=Path(str(output)+'.build.json')
    if output.exists() or not candidate.is_file() or not mapping.is_file():raise RuntimeError('Requires unpublished candidate and completed alias staging')
    lock=open(str(output)+'.repair.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    report=json.loads(report_path.read_text());build=json.loads(build_path.read_text())
    identity={'size':candidate.stat().st_size,'mtime_ns':candidate.stat().st_mtime_ns,'xref_md5':build['input_md5']['odb13v0_gene_xrefs.tab.gz']}
    if report.get('identity')!=identity or report.get('stages',{}).get('xrefs',{}).get('status')!='complete':raise RuntimeError('Cannot reuse unverified aliases or changed candidate')
    archive_status=json.loads((args.archives/'download-status.json').read_text())
    archive=args.archives/'odb13v0_gene_xrefs.tab.gz';item=archive_status['files'][archive.name]
    if archive_status.get('release')!='odb13v0' or item.get('status')!='verified' or item['md5']!=item['expected_md5'] or item['md5']!=identity['xref_md5'] or archive.stat().st_size!=item['bytes']:raise RuntimeError('Original verified v13 cross-reference source changed')
    if report.get('status') not in ('failed','repairing'):raise RuntimeError('Unexpected repair state')
    if args.source.resolve()!=Path(build['source_schema']).resolve():raise RuntimeError('Original schema source path mismatch')
    with readonly(args.source) as ref:schema=ref.execute(SCHEMA_QUERY).fetchall()
    with readonly(candidate) as ref:
        if ref.execute(SCHEMA_QUERY).fetchall()!=schema:raise RuntimeError('Candidate schema differs from reference')
    args.sources.mkdir(exist_ok=True);temp_dir=Path(str(output)+'.repair-tmp');temp_dir.mkdir(exist_ok=True);os.environ['SQLITE_TMPDIR']=str(temp_dir)
    if shutil.disk_usage(output.parent).free<24*GIB:raise RuntimeError('Require 24 GiB free for isolated repair')
    report.update(status='repairing',phase='symbols',symbol_strategy='NCBI GeneID + exact taxid, primary/authority symbols (unofficial synonyms retained in source only)',symbol_started_unix=int(time.time()));report.pop('error',None)
    def progress(message):
        report.update(message=message,updated_unix=int(time.time()));tmp=Path(str(report_path)+'.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(report_path);print(message,flush=True)
        if shutil.disk_usage(output.parent).free<8*GIB:raise RuntimeError('Disk reserve below 8 GiB; candidate remains unpublished')
    db=None;pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        progress('Downloading NCBI gene_info while streaming v13 GeneID links; reusing completed UniProt aliases')
        ncbi=args.sources/'gene_info.gz';download=pool.submit(fetch_gene_info,ncbi,args.proxy)
        db=sqlite3.connect(mapping,uri=True);db.executescript('PRAGMA journal_mode=DELETE; PRAGMA synchronous=NORMAL; PRAGMA cache_size=-65536; PRAGMA temp_store=FILE;')
        # Large throwaway inputs can be removed after their deduplicated aliases exist.
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'u','n'}.issubset(tables):raise RuntimeError('Alias staging is not at the audited pre-validation checkpoint')
        for table in ('raw_u','raw_n','fallback_n'):
            if table in tables:db.execute('DROP TABLE '+table)
        db.commit()
        stages=report.setdefault('symbol_stages',{})
        if stages.get('geneids',{}).get('status')!='complete':
            progress('Streaming v13 NCBI GeneID cross-references; retaining completed UniProt aliases')
            db.execute('DROP TABLE IF EXISTS raw_i');db.execute('DROP TABLE IF EXISTS i');db.execute('CREATE TABLE raw_i(gene_id INTEGER,orthodb_id INTEGER)');db.commit()
            stats=Path(str(output)+'.geneids.json');env=dict(os.environ,ORTHODB_STREAM_STATS=str(stats))
            proc=subprocess.Popen([str(args.streamer.resolve()),'geneids',str(args.archives/'odb13v0_gene_xrefs.tab.gz'),'2759'],stdout=subprocess.PIPE,env=env)
            count=0;batch=[]
            try:
                for line in proc.stdout:
                    packed,kind,value=line.decode().rstrip('\n').split('\t')
                    if kind!='I' or not value.isdigit() or int(value)<=0:raise RuntimeError('Invalid GeneID streamer record')
                    batch.append((int(value),int(packed)));count+=1
                    if len(batch)>=100000:db.executemany('INSERT INTO raw_i VALUES (?,?)',batch);batch.clear();db.commit()
                    if count%2000000==0:progress(f'NCBI GeneID links: {count:,} imported')
                if batch:db.executemany('INSERT INTO raw_i VALUES (?,?)',batch);db.commit()
                if proc.wait()!=0:raise RuntimeError('GeneID streamer failed')
            finally:
                proc.stdout.close()
                if proc.poll() is None:proc.terminate();proc.wait()
            stats_data=json.loads(stats.read_text())
            if stats_data['compatible_records']!=count:raise RuntimeError('GeneID link count mismatch')
            progress('Sorting and deduplicating NCBI GeneID links')
            db.execute('CREATE TABLE i(gene_id INTEGER,orthodb_id INTEGER,PRIMARY KEY(gene_id,orthodb_id)) WITHOUT ROWID')
            db.execute('INSERT OR IGNORE INTO i SELECT gene_id,orthodb_id FROM raw_i ORDER BY gene_id,orthodb_id');db.execute('DROP TABLE raw_i');db.commit()
            stages['geneids']={**stats_data,'status':'complete'};progress('NCBI GeneID links ready')
        progress('Waiting for the verified NCBI gene_info download')
        report['ncbi_source']=download.result()
        if stages.get('gene_info',{}).get('status')!='complete':
            progress('Loading NCBI primary symbols and authority names')
            count=load_gene_info(db,ncbi,progress);stages['gene_info']={'rows':count,'status':'complete'};progress('NCBI symbols loaded; gzip checksum verified')
        if stages.get('matched',{}).get('status')!='complete':
            progress('Matching GeneIDs to v13 genes with exact species agreement')
            counts=match_symbols(db,progress);stages['matched']={**counts,'status':'complete'};progress('Species-checked gene symbols staged')
        db.execute('ATTACH DATABASE ? AS baseline',(candidate.as_uri()+'?mode=ro',))
        samples=verify_samples(db,'baseline',aliases=True)
        if not any(row[2]==args.expected_ago_group for row in samples['Q9UL18']):raise RuntimeError('AGO1 group differs from independently verified v13 API group')
        report['sample_queries']=samples;progress('Human sample accessions/symbols and v13 memberships validated')
        # Build a separate disposable genes-only file, preserving u/n and their
        # completed checkpoints for a safe retry if validation/apply is interrupted.
        prepared=Path(str(output)+'.symbols.sqlite')
        if prepared.exists():raise RuntimeError('Prepared symbols file exists; inspect its recorded checkpoint before retrying')
        genes=sqlite3.connect(prepared,uri=True)
        try:
            genes.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-65536; PRAGMA temp_store=FILE;')
            last=[0.0]
            def guard():
                now=time.monotonic()
                if now-last[0]>10:
                    last[0]=now
                    return int(shutil.disk_usage(output.parent).free<8*GIB)
                return 0
            genes.set_progress_handler(guard,1000000)
            genes.execute('ATTACH DATABASE ? AS aliases',(mapping.as_uri()+'?mode=ro',))
            genes.execute(next(sql for kind,name,sql in schema if kind=='table' and name=='genes'))
            count1=genes.execute('INSERT INTO genes SELECT u.orthodb_id,u.value,n.value FROM aliases.u u LEFT JOIN aliases.n n USING(orthodb_id)').rowcount
            count2=genes.execute('INSERT INTO genes SELECT n.orthodb_id,NULL,n.value FROM aliases.n n WHERE NOT EXISTS(SELECT 1 FROM aliases.u u WHERE u.orthodb_id=n.orthodb_id)').rowcount
            genes.commit();report['gene_rows']=count1+count2
            if genes.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise RuntimeError('Prepared symbols failed quick_check')
        finally:genes.close()
        db.close();db=None;report['mapping_file']=str(prepared);report['phase']='mapping_ready'
        progress(f"Replacement genes ready: {report['gene_rows']:,} rows; reusable alias staging retained")
        if shutil.disk_usage(output.parent).free<max(16*GIB,prepared.stat().st_size*2+6*GIB):raise RuntimeError('Insufficient rollback/index reserve; use repair_v13_mappings.py --resume-staged')
        report['phase']='applying';progress('Replacing only candidate genes and their three indexes')
        samples=apply_mapping(candidate,prepared,schema,report['gene_rows'],build['stages']['memberships']['rows'],progress)
        with candidate.open('rb') as file:os.fsync(file.fileno())
        os.link(candidate,output);candidate.unlink()
        report.update(status='complete',phase='published',sample_queries=samples,bytes=output.stat().st_size);progress('Published validated separate v13 database; live database unchanged')
        build.update(status='complete',mapping_repair=str(report_path),sample_queries=samples,quick_check='ok',schema_matches_reference=True,bytes=output.stat().st_size)
        build['stages']['genes']={'rows':report['gene_rows'],'status':'complete','source':'v13 UniProt aliases plus NCBI gene_info exact GeneID/taxid symbols'};build.pop('error',None)
        tmp=Path(str(build_path)+'.tmp');tmp.write_text(json.dumps(build,indent=2)+'\n');tmp.replace(build_path)
    except BaseException as error:
        report.update(status='failed',error=str(error));tmp=Path(str(report_path)+'.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(report_path);raise
    finally:
        if db is not None:db.close()
        pool.shutdown(wait=True)
        lock.close()


if __name__=='__main__':main()
