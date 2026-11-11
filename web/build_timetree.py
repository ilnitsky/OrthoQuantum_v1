"""Induce dated OrthoDB cohorts; explicitly mark undated taxonomy placements."""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from timetree import parse_newick, leaves, normalize, prune


def build(catalog,taxonomy,newick,unresolved):
    original=parse_newick(newick);raw_rows=leaves(catalog['trees'][0]['tree']);by_name={normalize(r['name']):r for r in raw_rows}
    unresolved_names={normalize(re.sub(r'\s+\((?:not found in NCBI taxonomy|insufficient data in TimeTree to place this taxon)\)\s*$','',line)) for line in unresolved.splitlines() if line.strip()}
    direct=set();unmatched_tips=[];corrections=[]
    def convert(node):
        if node.get('lengthCorrection'):corrections.append({'label':node['name'],'originalLength':node['originalLength']})
        if node.get('children'):
            for child in node['children']:convert(child)
        else:
            row=by_name.get(normalize(node['name']))
            if row and normalize(row['name']) not in unresolved_names:
                if row['id'] in direct:raise ValueError('Ambiguous duplicate TimeTree tip for '+row['name'])
                label=node['name'];node.update(row);node.update(timetreeLabel=label,placement='timetree',inferredPlacement=False);direct.add(row['id'])
            else:unmatched_tips.append(node['name'])
    convert(original);master=prune(original,direct)
    if not master:raise ValueError('No TimeTree tips match the OrthoDB cohort')
    parents={};paths={};descendants={};taxon_tips={};row_by_id={r['id']:r for r in raw_rows}
    def ancestors(row):
        current=taxonomy['resolved'][row['id']];result=[]
        while current!=1:result.append(current);current=taxonomy['nodes'][str(current)]['parent']
        return result
    def index(node,parent=None,path=()):
        key=id(node);parents[key]=parent;path=path+(node,)
        if not node.get('children'):
            paths[node['id']]=path;subset={node['id']}
            for taxon in ancestors(node):taxon_tips.setdefault(taxon,set()).add(node['id'])
        else:subset=set().union(*(index(child,node,path) for child in node['children']))
        descendants[key]=subset;return subset
    index(master);placements={};audit=[];lca_cache={}
    def anchor_for(taxon,rank):
        key=(taxon,rank)
        if key in lca_cache:return lca_cache[key]
        support=taxon_tips.get(taxon,set());result=None
        if support:
            if len(support)==1:
                if rank in ('species','genus'):
                    tip=paths[next(iter(support))][-1];parent=parents[id(tip)]
                    if parent:result=(parent,tip,support)
            else:
                lineage=paths[next(iter(support))];common=set(map(id,lineage))
                for tip in support:common.intersection_update(map(id,paths[tip]))
                lca=next(node for node in reversed(lineage) if id(node) in common)
                if descendants[id(lca)]==support:result=(lca,lca['children'][-1],support)
        lca_cache[key]=result;return result
    for row in raw_rows:
        if row['id'] in direct:
            audit.append({'id':row['id'],'name':row['name'],'status':'timetree'});continue
        chosen=None
        for taxon in ancestors(row):
            rank=taxonomy['nodes'][str(taxon)]['rank']
            if rank not in ('species','genus','family'):continue
            anchor=anchor_for(taxon,rank)
            if anchor:chosen=(taxon,rank,anchor);break
        if not chosen:
            audit.append({'id':row['id'],'name':row['name'],'status':'excluded','reason':'No supported same-species/genus placement or monophyletic dated family'});continue
        taxon,rank,(parent,after,support)=chosen
        leaf={**row,'length':None,'inferredPlacement':True,'placement':'taxonomy-inferred','placementRank':rank,'placementTaxid':str(taxon),'placementName':taxonomy['nodes'][str(taxon)]['name'],'supportCount':len(support)}
        placements.setdefault((id(parent),id(after)),[]).append(leaf)
        audit.append({'id':row['id'],'name':row['name'],'status':'taxonomy-inferred','rank':rank,'taxid':taxon,'anchor':leaf['placementName'],'datedSupport':len(support)})
    def graft(node):
        if not node.get('children'):return
        children=[]
        for child in node['children']:
            graft(child);children.append(child);children.extend(sorted(placements.get((id(node),id(child)),[]),key=lambda r:r['name'].casefold()))
        node['children']=children
    graft(master)
    source={'sha256':hashlib.sha256((newick+'\0'+unresolved+'\0taxonomy-graft-v1').encode()).hexdigest(),'newickSha256':hashlib.sha256(newick.encode()).hexdigest(),'unresolvedSha256':hashlib.sha256(unresolved.encode()).hexdigest(),'branchLengthUnit':'Myr','negativeEdgeCorrections':corrections,'placementPolicy':'Undated polytomies at existing nodes supported by same-species/genus or monophyletic family; otherwise excluded. No inferred divergence ages.'}
    def root_age(node,distance=0):
        distance+=node.get('length') or 0
        if not node.get('children'):return 0 if node.get('inferredPlacement') else distance
        return max(root_age(child,distance) for child in node['children'])
    trees=[]
    for template in catalog['trees']:
        ids={r['id'] for r in leaves(template['tree'])};tree=prune(master,ids)
        dated=len(ids&direct)
        if not tree or not dated:
            trees.append({**template,'treeKind':'NCBI taxonomy (no dated coverage)','branchLengths':False,'timetreeSource':source,'coverage':{'dated':0,'inferred':0,'excluded':len(ids)}});continue
        rows=leaves(tree);inferred=sum(bool(r.get('inferredPlacement')) for r in rows)
        trees.append({**template,'name':template['name'].split(',')[0]+f', {len(rows):,} species','tree':tree,'treeKind':'TimeTree distances','speciesCount':len(rows),'originalSpeciesCount':len(ids),'genomeCount':sum(r.get('genomeCount',1) for r in rows),'rootAgeMyr':root_age(tree),'branchLengths':True,'branchLengthUnit':'Myr','timetreeSource':source,'coverage':{'dated':dated,'inferred':inferred,'excluded':len(ids)-len(rows)}})
    result={**catalog,'trees':trees,'timetreeSource':source,'placementAudit':audit,'unmatchedTimeTreeTips':unmatched_tips}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','taxonomy','newick','unresolved','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=build(json.loads(args.catalog.read_text()),json.loads(args.taxonomy.read_text()),args.newick.read_text(),args.unresolved.read_text())
    temp=args.output.with_suffix('.tmp');temp.write_text(json.dumps(result,separators=(',',':')));temp.replace(args.output)
    report={'source':result['timetreeSource'],'total':len(result['placementAudit']),'counts':{s:sum(r['status']==s for r in result['placementAudit']) for s in ('timetree','taxonomy-inferred','excluded')},'datedLevels':sum(t.get('branchLengths',False) for t in result['trees']),'unmatchedTimeTreeTips':len(result['unmatchedTimeTreeTips'])}
    args.output.with_suffix('.report.json').write_text(json.dumps(report,indent=2))
    args.output.with_suffix('.placements.tsv').write_text('taxid\tname\tstatus\tanchor\trank\n'+'\n'.join('\t'.join(str(r.get(k,'')) for k in ('id','name','status','anchor','rank')) for r in result['placementAudit'])+'\n')
    args.output.with_suffix('.excluded.txt').write_text('\n'.join(r['name'] for r in result['placementAudit'] if r['status']=='excluded')+'\n')
    print(json.dumps(report))
