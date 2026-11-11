"""Release-matched species sets; all unresolved taxonomy remains multifurcating."""
import copy
import json
from timetree import prune as prune_dated
from pathlib import Path

CATALOG_PATH=Path(__file__).parent/'public/data/trees-v13.json'


def leaves(node):
    if node.get('children'):
        return [leaf for child in node['children'] for leaf in leaves(child)]
    return [node] if node.get('id') else []


def dated_depths(node,distance=0):
    distance+=node.get('length') or 0
    if not node.get('children'):
        if not node.get('inferredPlacement'):yield distance
    else:
        for child in node['children']:yield from dated_depths(child,distance)


def catalog(legacy):
    data=json.loads(CATALOG_PATH.read_text());baseline=data
    timed_path=CATALOG_PATH.with_name('trees-timetree-v13.json')
    if timed_path.is_file():
        timed=json.loads(timed_path.read_text())
        if timed.get('ncbiSource',{}).get('sha256')==data.get('ncbiSource',{}).get('sha256'):data=timed
    trees=copy.deepcopy(data['trees'])
    full=next(tree for tree in trees if tree['clade']==2759)
    base_full=next(tree for tree in baseline['trees'] if tree['clade']==2759)
    representatives={leaf['id']:leaf for leaf in leaves(base_full['tree'])}
    # Old templates have historical taxonomy IDs; match them by v13 organism taxid
    # when the current NCBI taxid was renamed in the official species table.
    old_ids={leaf['organismId'].split('_')[0]:leaf for leaf in representatives.values()}
    compact=[]
    for old in legacy:
        if old['id'] not in ('1','3'):continue
        source=next(t for t in trees if t['clade']==old['clade'])
        seen=set()
        def project(node):
            if node.get('children'):
                children=[result for child in node['children'] if (result:=project(child))]
                return {**node,'children':children} if children else None
            match=representatives.get(str(node.get('id'))) or old_ids.get(str(node.get('id')))
            if not match or match['id'] in seen:return None
            seen.add(match['id']);return {**node,**match}
        if data.get('ncbiSource'):
            retained=set()
            for leaf in leaves(old['tree']):
                match=representatives.get(str(leaf.get('id'))) or old_ids.get(str(leaf.get('id')))
                if match:retained.add(match['id'])
            source=next(t for t in trees if t['clade']==old['clade'])
            def prune(node):
                if node.get('children'):
                    children=[child for raw in node['children'] if (child:=prune(raw))]
                    return {**node,'children':children} if children else None
                return node if node.get('id') in retained else None
            root=prune_dated(source['tree'],retained) if source.get('branchLengths') else prune(source['tree']);kind=source.get('treeKind','NCBI taxonomy')+' (compact cohort)'
        else:
            root=project(old['tree']);kind='Curated topology with v13 representative genomes'
        if root:
            count=len(leaves(root));compact.append({**old,'name':f"{'Eukaryota' if old['id']=='1' else 'Metazoa'} (compact), {count:,} species",'tree':root,'release':'v13','speciesCount':count,'genomeCount':sum(leaf['genomeCount'] for leaf in leaves(root)),'promoted':True,'treeKind':kind,'representativePolicy':full['representativePolicy'],'ncbiSource':data.get('ncbiSource'),**{k:source[k] for k in ('branchLengths','branchLengthUnit','timetreeSource') if k in source},'rootAgeMyr':max((distance for distance in dated_depths(root)),default=0),'coverage':{'dated':sum(not n.get('inferredPlacement',False) for n in leaves(root)),'inferred':sum(bool(n.get('inferredPlacement')) for n in leaves(root)),'excluded':len(retained)-count}})

    for tree in trees:
        tree['ncbiSource']=data.get('ncbiSource')
        if tree['clade']==2759:tree['id']='2';tree['name']='Eukaryota (extended), '+f"{tree['speciesCount']:,} species"
        elif tree['clade']==33208:tree['id']='111';tree['name']='Metazoa (extended), '+f"{tree['speciesCount']:,} species"
    return compact[:1]+trees[:2]+compact[1:]+trees[2:]+[tree for tree in legacy if tree['id']=='panther']
