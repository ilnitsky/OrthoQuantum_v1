"""Convert the pinned PANTHER species NHX tree without external packages."""
import csv
import json
import re
import xml.etree.ElementTree as ET


def species_table(path):
    with open(path,newline='') as source:
        rows=list(csv.DictReader(source,delimiter='\t'))
    result={}
    for row in rows:
        code=row['reference_proteome_short_name'];taxid=row['taxon_id'].removeprefix('NCBITaxon:')
        if not code or not taxid.isdigit() or code in result:raise ValueError('Invalid/duplicate species metadata')
        result[code]={'code':code,'name':row['organism'],'taxid':taxid,'common_name':row['common_name']}
    return result


def parse_nhx(text):
    position=0
    def spaces():
        nonlocal position
        while position<len(text) and text[position].isspace():position+=1
    def node(depth=0):
        nonlocal position
        if depth>256:raise ValueError('NHX tree too deep')
        spaces();out={'children':[],'name':''}
        if position<len(text) and text[position]=='(':
            position+=1
            while True:
                out['children'].append(node(depth+1));spaces()
                if position>=len(text):raise ValueError('Unclosed NHX clade')
                if text[position]==')':position+=1;break
                if text[position]!=',':raise ValueError('Expected NHX comma')
                position+=1
        start=position
        while position<len(text) and text[position] not in ',():;[':position+=1
        out['name']=text[start:position].strip()
        while position<len(text) and text[position] in ':[':
            if text[position]==':':
                position+=1;start=position
                while position<len(text) and text[position] not in ',();[':position+=1
                out['length']=float(text[start:position])
            else:
                end=text.find(']',position)
                if end<0:raise ValueError('Unclosed NHX annotation')
                annotation=text[position+1:end]
                match=re.search(r'(?:^|:)S=([^:]+)',annotation)
                if match:out['label']=match.group(1)
                position=end+1
        return out
    tree=node();spaces()
    # The pinned official v19 file ends after the root NHX annotation, without ';'.
    if position<len(text) and text[position]==';':position+=1;spaces()
    if position!=len(text):raise ValueError('Invalid NHX terminator')
    return tree


def active_species(species_path,nhx_path):
    metadata=species_table(species_path);root=parse_nhx(nhx_path.read_text());codes=[]
    def visit(node):
        if not node['children']:codes.append(node['name'])
        for child in node['children']:visit(child)
    visit(root)
    if len(codes)!=len(set(codes)) or not set(codes).issubset(metadata):raise ValueError('Tree has repeated or unknown species codes')
    # The official metadata also retains ASHGO/BRARP/ENTHI aliases not in the v19 tree.
    return {code:metadata[code] for code in codes}


def write_assets(species_path,nhx_path,destination):
    species=active_species(species_path,nhx_path);root=parse_nhx(nhx_path.read_text());seen=set()
    namespace='http://www.phyloxml.org';ET.register_namespace('',namespace)
    def element(parent,name,value=None):
        item=ET.SubElement(parent,'{'+namespace+'}'+name)
        if value is not None:item.text=str(value)
        return item
    xml=ET.Element('{'+namespace+'}phyloxml');phy=element(xml,'phylogeny');phy.set('rooted','true')
    element(phy,'name','PANTHER v19 species tree');element(phy,'description',f'PANTHER v19, {len(species)} species')
    mapping=[]
    def convert(parent,node):
        clade=element(parent,'clade')
        if 'length' in node:element(clade,'branch_length',node['length'])
        if node['children']:
            if node.get('label') or node['name']:element(clade,'name',node.get('label') or node['name'])
            for child in node['children']:convert(clade,child)
        else:
            code=node['name']
            if code not in species or code in seen:raise ValueError('Species tree/metadata mismatch: '+code)
            seen.add(code);record=species[code];element(clade,'name',record['name']);element(clade,'id',record['taxid']);mapping.append((code,record['taxid']))
    convert(phy,root)
    if seen!=set(species):raise ValueError('Species missing from v19 tree: '+str(set(species)-seen))
    if len({taxid for _,taxid in mapping})!=len(mapping):raise ValueError('Repeated species taxid cannot identify leaves uniquely')
    ET.ElementTree(xml).write(destination/'PANTHER.xml',encoding='utf-8',xml_declaration=True)
    with (destination/'prottree_id_converter.csv').open('w',newline='') as target:
        writer=csv.writer(target);writer.writerow(['Genome','TreeID']);writer.writerows(mapping)
    def as_json(node):
        if node['children']:
            return {'name':node.get('label') or node['name'],'children':[as_json(child) for child in node['children']]}
        record=species[node['name']]
        return {'id':record['taxid'],'name':record['name']}
    (destination/'tree.json').write_text(json.dumps({'id':'panther_v19','name':'PANTHER v19 species tree','tree':as_json(root)},separators=(',',':')))
    return species
