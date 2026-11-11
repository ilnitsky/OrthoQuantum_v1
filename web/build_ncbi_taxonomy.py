"""Extract just the required NCBI taxonomy and ancestors from a verified taxdump."""
import argparse
from array import array
import datetime
import hashlib
import io
import json
from pathlib import Path
import tarfile

SOURCE='https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz'


def extract(archive, checksum, targets):
    digest=hashlib.md5();sha=hashlib.sha256()
    with archive.open('rb') as source:
        for chunk in iter(lambda:source.read(8*1024*1024),b''):digest.update(chunk);sha.update(chunk)
    if digest.hexdigest()!=checksum:raise ValueError('NCBI taxdump checksum mismatch')
    parents=array('I',[0,1]);rank_codes=array('B',[0,0]);rank_names=['no rank'];merged={}
    with tarfile.open(archive,'r:gz') as dump:
        def lines(name):
            stream=dump.extractfile(name)
            if stream is None:raise ValueError('Missing NCBI member: '+name)
            return io.TextIOWrapper(stream)
        for line in lines('merged.dmp'):
            values=line.split('|');merged[int(values[0])]=int(values[1])
        for line in lines('nodes.dmp'):
            fields=line.split('|',3);taxid,parent=int(fields[0]),int(fields[1]);rank=fields[2].strip()
            if taxid>=len(parents):
                length=max(taxid+1,int(len(parents)*1.25)+1);parents.extend(array('I',[0])*(length-len(parents)));rank_codes.extend(array('B',[0])*(length-len(rank_codes)))
            if rank not in rank_names:rank_names.append(rank)
            parents[taxid]=parent;rank_codes[taxid]=rank_names.index(rank)
        def canonical(taxid):
            seen=set()
            while taxid in merged:
                if taxid in seen:raise ValueError('NCBI merge cycle')
                seen.add(taxid);taxid=merged[taxid]
            return taxid
        needed=set();resolutions={};missing=[]
        for original in sorted(targets):
            current=canonical(original)
            if current>=len(parents) or not parents[current]:missing.append(original);continue
            resolutions[str(original)]=current;seen=set()
            while current not in needed:
                if current in seen:raise ValueError('NCBI parent cycle')
                seen.add(current);needed.add(current)
                if current==1:break
                current=parents[current]
        names={}
        for line in lines('names.dmp'):
            fields=line.split('|');taxid=int(fields[0])
            if taxid in needed and fields[3].strip()=='scientific name':names[taxid]=fields[1].strip()
    if needed-set(names):raise ValueError('NCBI scientific names missing')
    nodes={str(i):{'parent':parents[i],'rank':rank_names[rank_codes[i]],'name':names[i]} for i in sorted(needed)}
    return {'source':SOURCE,'retrievedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'md5':digest.hexdigest(),'sha256':sha.hexdigest(),
            'nodes':nodes,'resolved':resolutions,'missingTaxids':missing,'targetCount':len(targets)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--checksum',type=Path,required=True);parser.add_argument('--catalog',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    catalog=json.loads(args.catalog.read_text());targets=set()
    def walk(node):
        if node.get('taxid'):targets.add(int(node['taxid']))
        if node.get('id'):targets.add(int(node['id']))
        for child in node.get('children',[]):walk(child)
    for tree in catalog['trees']:targets.add(tree['clade']);walk(tree['tree'])
    result=extract(args.archive,args.checksum.read_text().split()[0],targets)
    temporary=args.output.with_suffix('.tmp');temporary.write_text(json.dumps(result,separators=(',',':')));temporary.replace(args.output)
    print(json.dumps({'targets':result['targetCount'],'nodes':len(result['nodes']),'missing':result['missingTaxids'],'bytes':args.output.stat().st_size}))
