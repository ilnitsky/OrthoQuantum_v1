"""Release-specific read-only OrthoDB group metadata with bounded disk caching."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.parse

CACHE=Path(os.environ.get('ORTHODB_METADATA_CACHE','/tmp/orthoquantum-metadata'))


def number(value):
    if value is None or isinstance(value,bool):return None
    try:result=float(value)
    except (TypeError,ValueError):return None
    return result if math.isfinite(result) and result>=0 else None


def parse(group_id,release,payload):
    if not isinstance(payload,dict):raise ValueError('Invalid OrthoDB group response')
    data=payload.get('data')
    if payload.get('status')!='ok' or not isinstance(data,dict):raise ValueError('Invalid OrthoDB group response')
    ids=[data[key] for key in ('id','public_id') if data.get(key) is not None]
    if not ids or any(value!=group_id for value in ids):raise ValueError('OrthoDB returned a different group ID')
    profile=data.get('phyletic_profile') or {};architecture=data.get('gene_architecture') or {}
    if not isinstance(profile,dict):profile={}
    if not isinstance(architecture,dict):architecture={}
    fields={'evolutionaryRate':data.get('evolutionary_rate'),'medianProteinLength':architecture.get('protein_median_length'),
            'proteinLengthSD':architecture.get('protein_stdev_length'),'medianExonCount':architecture.get('exon_median_counts'),
            'exonCountSD':architecture.get('exon_stdev_counts'),'totalGenes':profile.get('gene_count'),
            'speciesPresent':profile.get('present_in'),'speciesCount':profile.get('species_count'),
            'singleCopySpecies':profile.get('single_copy'),'multiCopySpecies':profile.get('multi_copy')}
    return {'id':group_id,'release':release,'description':data.get('name'),'level':data.get('level_name'),**{key:number(value) for key,value in fields.items()}}


def fetch(group_id,release):
    path=CACHE/release/(group_id+'.json')
    if path.is_file():
        try:
            cached=json.loads(path.read_text())
            if cached['id']==group_id and cached['release']==release and time.time()-cached['fetchedAt']<7*86400:return cached['metadata']
        except (KeyError,ValueError,OSError):pass
    url=f'https://data.orthodb.org/{release}/group?'+urllib.parse.urlencode({'id':group_id})
    command=['curl','--fail','--silent','--show-error','--max-time','12','--max-filesize','4000000']
    if os.environ.get('ORTHODB_PROXY'):command+=['--proxy',os.environ['ORTHODB_PROXY']]
    response=subprocess.run(command+[url],capture_output=True,timeout=15,check=True)
    metadata=parse(group_id,release,json.loads(response.stdout))
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False) as output:
        json.dump({'id':group_id,'release':release,'fetchedAt':time.time(),'metadata':metadata},output);temp=Path(output.name)
    temp.replace(path);return metadata


def metadata(request):
    release=request.get('release');groups=request.get('groups')
    if release not in ('v11','v13'):raise ValueError('Choose a supported OrthoDB release')
    if not isinstance(groups,list) or not 1<=len(groups)<=20 or any(not isinstance(group,str) or not re.fullmatch(r'\d+at\d+',group) for group in groups):raise ValueError('Request 1–20 valid orthogroup IDs')
    values={};errors={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks={pool.submit(fetch,group,release):group for group in dict.fromkeys(groups)}
        for task in as_completed(tasks):
            group=tasks[task]
            try:values[group]=task.result()
            except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:errors[group]=type(error).__name__
    if CACHE.is_dir():
        files=sorted(CACHE.glob('*/*.json'),key=lambda p:p.stat().st_mtime)
        for old in files[:-2500]:old.unlink(missing_ok=True)
    return {'release':release,'groups':values,'errors':errors}
