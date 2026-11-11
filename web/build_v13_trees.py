"""Build release-matched taxonomy templates from verified v13 metadata, offline."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

from ncbi_order import NcbiTaxonomy

PRIORITY = [2759,33208,4751,33090,1206795,7742,2698737,33630,33634,2611352,2611341,554915,5794,5878,33682,2608109,2763,3027]
COLORS = {33208:'#ad5e7a',4751:'#a574b1',33090:'#51a579',2698737:'#52a6b5',2611352:'#cd9c4c',2611341:'#b58e70',554915:'#9b9b54'}


def verified_rows(root, name, status):
    path=root/f'odb13v0_{name}.tab.gz';info=status['files'][path.name]
    if info['status']!='verified' or hashlib.md5(path.read_bytes()).hexdigest()!=info['expected_md5']:
        raise ValueError('Unverified metadata: '+path.name)
    with gzip.open(path,'rt') as source:
        return [line.rstrip('\n').split('\t') for line in source]


def build(root, taxonomy_path=None):
    taxonomy=NcbiTaxonomy(json.loads(taxonomy_path.read_text())) if taxonomy_path else None
    status=json.loads((root/'download-status.json').read_text())
    if status['release']!='odb13v0':raise ValueError('Expected v13 metadata')
    levels={int(r[0]):{'name':r[1],'groups':int(r[3] or 0)} for r in verified_rows(root,'levels',status)}
    organisms={r[1]:{'id':r[0],'name':r[2],'organismId':r[1],'assembly':r[3],'clustered':r[6]=='C'} for r in verified_rows(root,'species',status)}
    paths={r[1]:list(map(int,r[3].strip('{}').split(','))) for r in verified_rows(root,'level2species',status) if r[0]=='2759'}
    # One clustered representative per current NCBI species; do not count alternate
    # assemblies as additional species or pool their genes into copy counts.
    grouped=collections.defaultdict(list)
    for organism,path in paths.items():
        if organism in organisms and organisms[organism]['clustered']:
            grouped[organisms[organism]['id']].append((organism,path))
    selected=[]
    for variants in grouped.values():
        organism,path=min(variants,key=lambda item:(int(item[0].split('_')[1]),int(item[0].split('_')[0])))
        selected.append({**organisms[organism],'path':path,'genomeCount':len(variants)})
    available={i for leaf in selected for i in leaf['path'] if i in levels and levels[i]['groups']>0}

    def tree_for(level):
        root_node={'name':levels[level]['name'],'taxid':str(level),'children':[]};nodes={():root_node}
        members=[leaf for leaf in selected if level in leaf['path']]
        for leaf in sorted(members,key=lambda r:(r['name'].casefold(),r['id'])):
            lineage=leaf['path'][leaf['path'].index(level)+1:]
            # Terminal taxon is the species itself; intermediate nodes are official
            # v13 orthology levels. Unresolved relationships remain polytomies.
            lineage=[i for i in lineage if i in levels and str(i)!=leaf['id']]
            prefix=();parent=root_node;color=COLORS.get(level,'#9a7882')
            for ancestor in lineage:
                color=COLORS.get(ancestor,color);prefix+= (ancestor,)
                if prefix not in nodes:
                    nodes[prefix]={'name':levels[ancestor]['name'],'taxid':str(ancestor),'color':color,'children':[]};parent['children'].append(nodes[prefix])
                parent=nodes[prefix]
            parent['children'].append({k:leaf[k] for k in ('id','name','organismId','assembly','genomeCount')}|{'color':color})
        ncbi_report={}
        if taxonomy:root_node,ncbi_report=taxonomy.tree(level,members,COLORS)
        return {'id':f'v13-{level}','clade':level,'name':f"{'SAR' if level==2698737 else levels[level]['name']}, {len(members):,} species",'tree':root_node,
                'promoted':level in PRIORITY,'release':'v13','treeKind':'NCBI taxonomy' if taxonomy else 'OrthoDB v13 taxonomy','ncbiTaxonomy':ncbi_report,'speciesCount':len(members),
                'genomeCount':sum(leaf['genomeCount'] for leaf in members),'representativePolicy':'One clustered genome per NCBI species; lowest organism suffix, then source taxid.'}
    ordered=[i for i in PRIORITY if i in available]+sorted(available-set(PRIORITY),key=lambda i:levels[i]['name'].casefold())
    return {'ncbiSource':{key:taxonomy.snapshot[key] for key in ('source','retrievedAt','md5','sha256')} if taxonomy else None,'release':'v13','taxonomySource':'NCBI parent hierarchy with verified OrthoDB v13 cohorts' if taxonomy else 'Verified odb13v0 levels/species/level2species dumps','trees':[tree_for(i) for i in ordered],
            'sourceMd5':{name:status['files'][f'odb13v0_{name}.tab.gz']['expected_md5'] for name in ('levels','species','level2species')},
            'speciesCount':len(selected),'genomeCount':len(paths)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archives',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--taxonomy',type=Path,default=Path(__file__).parent/'public/data/ncbi-taxonomy-v13.json');args=parser.parse_args()
    catalog=build(args.archives,args.taxonomy);temporary=args.output.with_suffix('.tmp');temporary.write_text(json.dumps(catalog,separators=(',',':')));temporary.replace(args.output)
    print(json.dumps({'levels':len(catalog['trees']),'species':catalog['speciesCount'],'genomes':catalog['genomeCount'],'bytes':args.output.stat().st_size}))
