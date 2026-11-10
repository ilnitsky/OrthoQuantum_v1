"""Export the existing reference tree templates; no database or network access."""
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
DATA=HERE/'public/data'


def convert_file(path):
    root=ET.parse(path).getroot()
    def tag(element):return element.tag.rsplit('}',1)[-1]
    def child(element,name):return next((e for e in element if tag(e)==name),None)
    def text(element,name):
        node=child(element,name)
        return node.text if node is not None and node.text else ''
    colors={t.get('code'):text(t,'color').replace('0x','#') for t in root.iter() if tag(t)=='taxonomy' and t.get('code')}
    phy=next(e for e in root if tag(e)=='phylogeny')
    def walk(element,inherited='#9a7882'):
        taxonomy=child(element,'taxonomy')
        color=colors.get(text(taxonomy,'code') if taxonomy is not None else '',inherited)
        node={'name':text(element,'name'),'id':text(element,'id'),'color':color}
        nested=[walk(e,color) for e in element if tag(e)=='clade']
        if nested:node['children']=nested
        length=element.get('branch_length') or text(element,'branch_length')
        if length:node['length']=float(length)
        return node
    return {'name':text(phy,'description') or path.stem,'title':text(phy,'name'),'tree':walk(child(phy,'clade'))}


if __name__=='__main__':
    trees=[]
    for tree_id,clade in [('1',2759),('2',2759),('3',33208),('111',33208)]:
        path=next((REPO/'worker/app/phyloxml').glob(tree_id+'_*.xml'))
        tree=convert_file(path);tree.update(id=tree_id,clade=clade);trees.append(tree)
    tree=convert_file(REPO/'worker/app/panther/PANTHER.xml');tree.update(id='panther',clade=0);trees.append(tree)
    DATA.mkdir(exist_ok=True)
    (DATA/'trees.json').write_text(json.dumps(trees,separators=(',',':')))
    with (REPO/'worker/app/panther/prottree_id_converter.csv').open() as source:
        mapping={r['Genome']:r['TreeID'] for r in csv.DictReader(source)}
    (DATA/'panther-species.json').write_text(json.dumps(mapping))
    print('Exported',len(trees),'reference trees')
