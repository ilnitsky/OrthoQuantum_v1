"""Plain text OrthoDB row names and NCBI species-rank names for TimeTree upload."""
import json
from pathlib import Path

ROOT=Path(__file__).parent


def export(catalog,taxonomy,destination):
    destination.mkdir(parents=True,exist_ok=True);summary={}
    def leaves(node):return [leaf for child in node['children'] for leaf in leaves(child)] if node.get('children') else [node]
    for clade,label in [(2759,'eukaryota'),(33208,'metazoa')]:
        tree=next(t for t in catalog['trees'] if t['clade']==clade);rows=leaves(tree['tree']);names=[];mapping=[]
        for leaf in rows:
            taxid=taxonomy['resolved'].get(leaf['id']);species=None;seen=set()
            while taxid and taxid!=1:
                if taxid in seen:raise ValueError('Taxonomy cycle')
                seen.add(taxid);node=taxonomy['nodes'][str(taxid)]
                if node['rank']=='species':species=(taxid,node['name']);break
                taxid=node['parent']
            if species:names.append(species[1])
            mapping.append([leaf['id'],leaf['name'],str(species[0]) if species else '',species[1] if species else ''])
        exact='\n'.join(leaf['name'] for leaf in rows)+'\n';unique=list(dict.fromkeys(names))
        (destination/f'orthodb-v13-{label}-all.txt').write_text(exact)
        (destination/f'timetree-{label}.txt').write_text('\n'.join(unique)+'\n')
        (destination/f'timetree-{label}-mapping.tsv').write_text('OrthoDB_taxid\tOrthoDB_name\tNCBI_species_taxid\tNCBI_species_name\n'+'\n'.join('\t'.join(row) for row in mapping)+'\n')
        summary[label]={'rows':len(rows),'timetreeSpecies':len(unique),'rowsWithoutSpeciesRank':sum(not row[2] for row in mapping)}
    (destination/'manifest.json').write_text(json.dumps({'taxonomySource':catalog['ncbiSource'],'lists':summary},indent=2)+'\n');return summary


if __name__=='__main__':
    print(json.dumps(export(json.loads((ROOT/'public/data/trees-v13.json').read_text()),json.loads((ROOT/'public/data/ncbi-taxonomy-v13.json').read_text()),ROOT/'public/data/species')))
