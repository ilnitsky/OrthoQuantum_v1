#!/usr/bin/env python3
"""Publish missing v13 memberships in a separate immutable supplement."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','archives','catalog','streamer','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();staging=Path(str(out)+'.building');report_path=Path(str(out)+'.json')
    lock=open(str(out)+'.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if out.exists() or staging.exists():raise RuntimeError('Refusing to overwrite supplement or unfinished staging')
    base=args.base.resolve();stat=base.stat();report={'status':'building','release':'v13','base':{'bytes':stat.st_size,'mtimeNs':stat.st_mtime_ns},'startedUnix':int(time.time())}
    def progress(message,**fields):
        report.update(message=message,updatedUnix=int(time.time()),**fields);temp=Path(str(report_path)+'.tmp');temp.write_text(json.dumps(report,indent=2));temp.replace(report_path);print(message,flush=True)
    try:
        with sqlite3.connect(base.as_uri()+'?mode=ro',uri=True) as source:existing={row[0] for row in source.execute('SELECT level_id FROM levels')}
        catalog=json.loads(args.catalog.read_text());missing={tree['clade']:tree['tree']['name'] for tree in catalog['trees'] if tree['clade'] not in existing}
        if not missing:raise RuntimeError('No missing levels to import')
        status=json.loads((args.archives/'download-status.json').read_text());name='odb13v0_OG2genes.tab.gz';info=status['files'][name];archive=args.archives/name
        if status['release']!='odb13v0' or info['status']!='verified' or info['md5']!=info['expected_md5'] or archive.stat().st_size!=info['bytes']:raise RuntimeError('Archive differs from verified v13 input')
        progress('Verifying membership archive',levels=missing)
        digest=hashlib.md5()
        with archive.open('rb') as source:
            for chunk in iter(lambda:source.read(8*1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=info['expected_md5']:raise RuntimeError('Membership MD5 mismatch')
        report['archiveMd5']=digest.hexdigest()
        db=sqlite3.connect(staging);db.executescript('PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL; PRAGMA cache_size=-32768; CREATE TABLE levels(level_id INTEGER PRIMARY KEY,scientific_name TEXT NOT NULL); CREATE TABLE orthodb_to_og(orthodb_id INTEGER NOT NULL,cluster_id INTEGER NOT NULL,clade INTEGER NOT NULL);')
        db.executemany('INSERT INTO levels VALUES (?,?)',missing.items());db.commit()
        progress('Streaming only missing v13 levels',rows=0)
        process=subprocess.Popen([str(args.streamer),'memberships',str(archive),','.join(map(str,missing))],stdout=subprocess.PIPE,text=True)
        try:
            rows=0;batch=[]
            for line in process.stdout:
                fields=line.rstrip().split('\t')
                if len(fields)!=3:raise RuntimeError('Malformed membership record')
                batch.append(tuple(map(int,fields)));rows+=1
                if len(batch)==10000:db.executemany('INSERT INTO orthodb_to_og VALUES (?,?,?)',batch);db.commit();batch=[]
                if rows%500000==0:progress(f'Missing-level memberships: {rows:,}',rows=rows)
            if batch:db.executemany('INSERT INTO orthodb_to_og VALUES (?,?,?)',batch);db.commit()
            if process.wait():raise RuntimeError('Membership streamer failed')
        finally:
            if process.poll() is None:process.terminate();process.wait()
        progress('Indexing missing-level memberships',rows=rows)
        db.execute('CREATE INDEX membership_group_idx ON orthodb_to_og(clade,cluster_id)');db.execute('CREATE INDEX membership_gene_idx ON orthodb_to_og(orthodb_id,clade)');db.commit()
        counts=dict(db.execute('SELECT clade,count(*) FROM orthodb_to_og GROUP BY clade'))
        if set(counts)!=set(missing):raise RuntimeError('One or more levels have no memberships')
        progress('Checking supplement integrity',levelRows=counts)
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise RuntimeError('Supplement failed quick_check')
        db.execute('ANALYZE');db.commit();db.close()
        if (base.stat().st_size,base.stat().st_mtime_ns)!=(stat.st_size,stat.st_mtime_ns):raise RuntimeError('Base reference changed during build')
        with staging.open('rb') as source:os.fsync(source.fileno())
        os.link(staging,out);staging.unlink();progress('Published validated missing-level supplement',status='complete',quickCheck='ok',bytes=out.stat().st_size)
    except BaseException as error:progress('Supplement build failed',status='failed',error=str(error));raise
    finally:lock.close()


if __name__=='__main__':main()
