#!/usr/bin/env python3
"""Resumable v13 SPARQL bulk rate/architecture export; never modifies live DBs."""
import argparse
import fcntl
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time

ENDPOINT='https://sparql.orthodb.org/sparql'
FIELDS={'rate':'ogEvolRate','median_length':'ogMedianProteinLength','length_sd':'ogStddevProteinLength','median_exons':'ogMedianExonsCount','exon_sd':'ogStddevExonsCount'}

def query_text(level,last='',limit=5000):
    if not str(level).isdigit() or (last and not re.fullmatch(r'\d+at\d+',last)):raise ValueError('Invalid query cursor')
    cursor=f'FILTER(STR(?og) > "http://purl.orthodb.org/odbgroup/{last}")' if last else ''
    optional=' '.join(f'OPTIONAL {{ ?og odb:{predicate} ?{key} }}' for key,predicate in FIELDS.items() if key!='rate')
    return f'PREFIX odb: <http://purl.orthodb.org/> SELECT ?og '+ ' '.join('?'+k for k in FIELDS)+f' WHERE {{ ?og odb:ogBuiltAt <http://purl.uniprot.org/taxonomy/{level}>; odb:ogEvolRate ?rate . {cursor} {optional} }} ORDER BY STR(?og) LIMIT {int(limit)}'

def parse_rows(bindings,level,last=''):
    rows=[]
    for record in bindings:
        uri=record['og']['value'];group=uri.removeprefix('http://purl.orthodb.org/odbgroup/') if hasattr(str,'removeprefix') else uri.split('/')[-1]
        if uri!='http://purl.orthodb.org/odbgroup/'+group or not re.fullmatch(r'\d+at'+str(level),group) or group<=last:raise ValueError('Invalid/out-of-order group cursor')
        values=[]
        for key in FIELDS:
            raw=record.get(key,{}).get('value');value=None if raw is None else float(raw)
            if value is not None and (not math.isfinite(value) or value<0):raise ValueError('Invalid metadata number')
            values.append(value)
        if values[0] is None:raise ValueError('Missing required rate')
        rows.append((group,int(level),*values));last=group
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--levels',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--proxy',default='socks5h://127.0.0.1:10808');p.add_argument('--page-size',type=int,default=5000);args=p.parse_args()
    if not 1<=args.page_size<=10000:raise ValueError('Page size must be 1–10000')
    args.output.mkdir(parents=True,exist_ok=True);lock=(args.output/'.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    db=sqlite3.connect(args.output/'metadata.sqlite');db.execute('PRAGMA journal_mode=WAL');db.executescript('CREATE TABLE IF NOT EXISTS metadata(group_id TEXT PRIMARY KEY,level INTEGER,rate REAL,median_length REAL,length_sd REAL,median_exons REAL,exon_sd REAL);CREATE TABLE IF NOT EXISTS levels(level INTEGER PRIMARY KEY,name TEXT,cursor TEXT DEFAULT "",rows INTEGER DEFAULT 0,complete INTEGER DEFAULT 0);CREATE TABLE IF NOT EXISTS provenance(key TEXT PRIMARY KEY,value TEXT);')
    with gzip.open(args.levels,'rt') as f:levels=[line.strip().split('\t') for line in f if line.strip()]
    priority={'2759':0,'33208':1,'4751':2,'33090':3};levels.sort(key=lambda r:(priority.get(r[0],4),int(r[0])))
    db.executemany('INSERT OR IGNORE INTO levels(level,name) VALUES (?,?)',[(int(r[0]),r[1]) for r in levels]);db.commit()
    state={'release':'v13','endpoint':ENDPOINT,'status':'starting','rows':0,'total_levels':len(levels),'expected_groups_all':sum(int(r[3]) for r in levels if len(r)>3),'note':'Only groups with an upstream rate are exported; all-group count is not the expected number of rates.'}
    def progress(**extra):
        state.update(extra);state['updated_unix']=int(time.time());state['rows']=db.execute('SELECT COALESCE(SUM(rows),0) FROM levels').fetchone()[0];state['completed_levels']=db.execute('SELECT COUNT(*) FROM levels WHERE complete=1').fetchone()[0]
        temp=args.output/'progress.json.tmp';temp.write_text(json.dumps(state,indent=2)+'\n');temp.replace(args.output/'progress.json')
        print(f"{state['status']}: {state['rows']:,} rates; {state['completed_levels']}/{state['total_levels']} levels; {state.get('level_name','')} {state.get('message','')}",flush=True)
    def request(query=None):
        for attempt in range(6):
            progress(status='requesting',attempt=attempt+1)
            try:
                with tempfile.TemporaryDirectory() as root:
                    header=Path(root)/'headers';body=Path(root)/'body';cmd=['curl','--fail','--silent','--show-error','--max-time','120','--max-filesize','30000000','--proxy',args.proxy,'--dump-header',str(header),'--output',str(body)]
                    if query is None:cmd+=['https://sparql.orthodb.org/']
                    else:
                        qfile=Path(root)/'query';qfile.write_text(query);cmd+=['--get','--data-urlencode','query@'+str(qfile),'--data-urlencode','format=application/sparql-results+json','--data-urlencode','timeout=90000',ENDPOINT]
                    subprocess.run(cmd,check=True,timeout=130,capture_output=True)
                    headers=header.read_text().lower()
                    if 'x-sql-message' in headers or 'x-sparql-maxrows' in headers:raise ValueError('Endpoint reported incomplete results')
                    raw=body.read_text()
                    return raw if query is None else json.loads(raw)['results']['bindings']
            except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
                progress(status='retrying',message=f'{type(error).__name__}: {str(error)[:250]}')
                if attempt==5:raise
                time.sleep(min(60,5*2**attempt))
    def verify():
        page=request()
        if not re.search(r'OrthoDB release\s*13\.0',page,re.I):raise ValueError('SPARQL no longer advertises verified release 13.0')
        sample=request('SELECT ?rate WHERE { <http://purl.orthodb.org/odbgroup/6005769at2759> <http://purl.orthodb.org/ogEvolRate> ?rate }')
        if len(sample)!=1 or abs(float(sample[0]['rate']['value'])-2.5192)>1e-6:raise ValueError('Known v13 sample does not match')
        db.execute('INSERT OR REPLACE INTO provenance VALUES (?,?)',('release','v13'));db.execute('INSERT OR REPLACE INTO provenance VALUES (?,?)',('endpoint',ENDPOINT));db.execute('INSERT OR REPLACE INTO provenance VALUES (?,?)',('frontend_sha256',hashlib.sha256(page.encode()).hexdigest()));db.commit()
    try:
        verify();pages=0
        for raw in levels:
            level=int(raw[0]);cursor,count,complete=db.execute('SELECT cursor,rows,complete FROM levels WHERE level=?',(level,)).fetchone()
            if complete:continue
            progress(level=level,level_name=raw[1],cursor=cursor,message='')
            while True:
                if pages and pages%50==0:verify()
                bindings=request(query_text(level,cursor,args.page_size));rows=parse_rows(bindings,level,cursor)
                if len(rows)>args.page_size:raise ValueError('Unexpected oversized page')
                with db:
                    db.executemany('INSERT INTO metadata VALUES (?,?,?,?,?,?,?)',rows)
                    if rows:cursor=rows[-1][0]
                    count+=len(rows);complete=int(len(rows)<args.page_size)
                    db.execute('UPDATE levels SET cursor=?,rows=?,complete=? WHERE level=?',(cursor,count,complete,level))
                pages+=1;progress(status='downloading',cursor=cursor,message=f'level rows {count:,}')
                if complete:break
                time.sleep(1)
        progress(status='validating',message='SQLite quick_check');result=db.execute('PRAGMA quick_check').fetchone()[0]
        if result!='ok':raise ValueError(result)
        db.execute('CREATE INDEX IF NOT EXISTS metadata_level_idx ON metadata(level)');db.execute('PRAGMA wal_checkpoint(TRUNCATE)');progress(status='complete',message='All levels processed; available rates saved')
    except Exception as error:
        progress(status='failed',message=f'{type(error).__name__}: {error}');raise
    finally:db.close()
if __name__=='__main__':main()
