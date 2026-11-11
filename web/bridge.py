from query_input import parse_inputs
"""Isolated, read-only SQLite adapter. NDJSON progress in; no Dash/Redis imports."""
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

from v13_catalog import catalog as v13_catalog

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'public/data'
TREES = json.loads((DATA / 'trees.json').read_text())
DB_PATH = Path(os.environ.get('ORTHODB_PATH', '/home/ilnitsky/PANTHERDB/orthodb.db'))
PANTHER_PATH = Path(os.environ.get('PANTHER_PATH', '/home/ilnitsky/PANTHERDB/panther.sqlite'))
RELEASE = os.environ.get('ORTHODB_RELEASE', 'v11')
LEVELS_PATH = Path(os.environ.get('ORTHODB_LEVELS_PATH', str(DB_PATH.with_name('orthodb_v13_levels.sqlite'))))
V13_TREES = v13_catalog(TREES) if RELEASE == 'v13' else None
COMMON = (9606, 10090, 7955, 7227, 6239, 10116, 9031, 8364, 4932, 3702)
TRANSLATION = {441894:8801,381198:8845,216574:8962,74533:9694,62698:9708,310752:9767,127582:9778,73337:9807,1230840:9818,43346:9901,299123:40157,556262:100884,319938:288004,1841481:302047,1505932:408180,595593:656366,667632:863227,1336249:1367849,1220582:1368415,1834200:1796646,1166016:1905730}


def emit(kind, **values):
    print(json.dumps({'type': kind, **values}, separators=(',', ':')), flush=True)


def leaves(node):
    if not node.get('children'):
        return [{'id': str(node['id']), 'name': node['name'], **{key:node[key] for key in ('organismId','assembly','genomeCount','ncbiTaxid','ncbiScientificName','taxonomyStatus','inferredPlacement','placement','placementRank','placementName') if key in node}}] if node.get('id') else []
    return [leaf for child in node['children'] for leaf in leaves(child)]


def get_tree(tree_id):
    tree = next((t for t in (V13_TREES or TREES) if t['id'] == str(tree_id)), None)
    if tree is None:
        raise ValueError('Unknown tree selection')
    return tree


class QueryBudgetConnection(sqlite3.Connection):
    """Limit each SQL statement, excluding upstream requests and Python work."""
    def execute(self, *args, **kwargs):
        self.query_deadline=time.monotonic()+120
        return super().execute(*args, **kwargs)


def connect(path):
    if not path.is_file():
        raise ValueError(f'Reference database is unavailable: {path.name}. Bundled demos and file import still work.')
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, factory=QueryBudgetConnection)
    conn.execute('PRAGMA query_only=ON')
    conn.execute('PRAGMA cache_size=-16384')
    if path.resolve() == DB_PATH.resolve() and RELEASE == 'v13' and LEVELS_PATH.is_file():
        manifest_path = Path(str(LEVELS_PATH)+'.json')
        if manifest_path.is_file():
            manifest=json.loads(manifest_path.read_text());base=DB_PATH.stat()
            if manifest.get('status')=='complete' and manifest.get('release')=='v13' and manifest.get('quickCheck')=='ok' and manifest.get('base')=={'bytes':base.st_size,'mtimeNs':base.st_mtime_ns}:
                conn.execute('ATTACH DATABASE ? AS extra',(LEVELS_PATH.resolve().as_uri()+'?mode=ro',))
    conn.set_progress_handler(lambda: int(time.monotonic() > conn.query_deadline), 10000)
    return conn


def membership_table(conn, clade):
    attached=any(row[1]=='extra' for row in conn.execute('PRAGMA database_list'))
    if attached and conn.execute('SELECT 1 FROM extra.levels WHERE level_id=?',(clade,)).fetchone():
        return 'extra.orthodb_to_og'
    if RELEASE=='v13' and not conn.execute('SELECT 1 FROM main.levels WHERE level_id=?',(clade,)).fetchone():
        raise ValueError('This v13 orthology level is not available yet. Refresh after its supplement is published.')
    return 'main.orthodb_to_og'


def panther_reference():
    bundle = os.environ.get('PANTHER_BUNDLE_DIR')
    if bundle and (Path(bundle) / 'manifest.json').is_file():
        root = Path(bundle)
        manifest = json.loads((root / 'manifest.json').read_text())
        if manifest.get('status') != 'complete' or manifest.get('release') != 'PANTHER19.0':
            raise ValueError('PANTHER v19 bundle has not passed validation')
        with (root / 'prottree_id_converter.csv').open() as source:
            mapping = {row['Genome']: row['TreeID'] for row in csv.DictReader(source)}
        if (root / 'tree.json').is_file():
            tree = json.loads((root / 'tree.json').read_text())
        else:
            ns = '{http://www.phyloxml.org}'
            phy = ET.parse(root / 'PANTHER.xml').getroot().find(ns + 'phylogeny')
            def convert(node):
                children = node.findall(ns + 'clade')
                result = {'name': node.findtext(ns + 'name', '')}
                if children:
                    result['children'] = [convert(child) for child in children]
                else:
                    result['id'] = node.findtext(ns + 'id', '')
                return result
            tree = {'id': 'panther_v19', 'tree': convert(phy.find(ns + 'clade'))}
        return {'database': root / 'panther.sqlite', 'tree': tree,
                'mapping': mapping, 'release': 'v19', 'relationships': root / 'relationships.sqlite'}
    return {'database': PANTHER_PATH, 'tree': get_tree('panther'),
            'mapping': json.loads((DATA / 'panther-species.json').read_text()),
            'release': 'local dataset (release unspecified)', 'relationships': None}


def config():
    if RELEASE == 'v13':
        report_path = Path(str(DB_PATH)+'.build.json')
        report = json.loads(report_path.read_text())
        if report.get('status') != 'complete' or report.get('release') != 'odb13v0' or report.get('quick_check') != 'ok' or not report.get('schema_matches_reference'):
            raise ValueError('OrthoDB v13 has not passed publication validation')
    with connect(DB_PATH) as conn:
        supported = {row[0] for row in conn.execute('SELECT level_id FROM levels')}
        if any(row[1]=='extra' for row in conn.execute('PRAGMA database_list')):
            supported.update(row[0] for row in conn.execute('SELECT level_id FROM extra.levels'))
    result = []
    for tree in (V13_TREES or TREES):
        if tree['id'] == 'panther' or tree['clade'] not in supported:
            continue
        species = [s for s in leaves(tree['tree']) if s['id'].isdigit()]
        species.sort(key=lambda s: (COMMON.index(int(s['id'])) if s['id'].isdigit() and int(s['id']) in COMMON else len(COMMON), s['name'].lower()))
        result.append({'id': tree['id'], 'name': tree['name'], 'clade': tree['clade'], 'species': species, 'promoted':tree.get('promoted',True), 'treeKind':tree.get('treeKind','Curated topology'), 'genomeCount':tree.get('genomeCount'), 'representativePolicy':tree.get('representativePolicy')})
    reference = panther_reference()
    return {'trees': result, 'databaseAvailable': DB_PATH.is_file(), 'pantherAvailable': reference['database'].is_file(), 'pantherRelease': reference['release'], 'pantherOrthologsAvailable': bool(reference['relationships'] and reference['relationships'].is_file()), 'release': RELEASE, 'timetreeAvailable':any(t.get('branchLengths') for t in (V13_TREES or []))}


def remote_search(query, clade, taxid, limit=100):
    # Fixed endpoint; retrieve additional pages when the requested limit exceeds the upstream page size.
    if not re.fullmatch(r'v\d+', RELEASE):
        raise ValueError('Invalid configured OrthoDB release')
    records, seen, total = [], set(), 0
    while len(records) < limit:
        parameters = {'query': query, 'level': clade, 'species': taxid,
                      'take': min(1000, limit-len(records)), 'skip': len(records)}
        url = f'https://data.orthodb.org/{RELEASE}/search?' + urllib.parse.urlencode(parameters)
        command = ['curl', '--fail', '--silent', '--show-error', '--max-time', '25', '--max-filesize', '4000000']
        proxy = os.environ.get('ORTHODB_PROXY', '')
        if proxy:
            command += ['--proxy', proxy]
        raw = subprocess.run(command + [url], capture_output=True, timeout=30, check=True).stdout
        data = json.loads(raw)
        if data.get('status') != 'ok':
            raise ValueError('OrthoDB search did not return a successful response')
        total = int(data.get('count') or 0)
        page = data.get('bigdata') or []
        fresh = [r for r in page if r.get('id') not in seen]
        if not fresh:
            break
        for record in fresh:
            if record.get('id') not in seen:
                seen.add(record.get('id'));records.append(record)
                if len(records) == limit:
                    break
        if len(records) >= total:
            break
    return records, total


def lookup_index(conn, table, column):
    """Pin lookups to existing indexes; never add live indexes."""
    schema, name=table.split('.')
    for index in conn.execute(f'PRAGMA {schema}.index_list("{name}")').fetchall():
        escaped=index[1].replace('"','""')
        columns=conn.execute(f'PRAGMA {schema}.index_info("{escaped}")').fetchall()
        if columns and columns[0][2]==column:return f' INDEXED BY "{escaped}"'
    return ''  # Tiny unindexed fixtures / legacy schema compatibility.


def reference_name_lookup(conn, taxid, organism_id=None):
    """Load reference names once; read/cache contiguous membership groups."""
    if organism_id:
        tax, suffix=map(int,organism_id.split('_'));lower=tax<<32|suffix<<24;upper=lower+(1<<24)
    else:lower=taxid<<32;upper=(taxid+1)<<32
    genes={}
    hint=lookup_index(conn,'main.genes','orthodb_id')
    for gene,name in conn.execute(f'SELECT orthodb_id,gene_name FROM main.genes{hint} WHERE orthodb_id>=? AND orthodb_id<?',(lower,upper)):
        if name:genes.setdefault(gene,set()).update(part.strip() for part in name.split(';') if part.strip())
    groups={};tables={}
    def lookup(group_id):
        cluster,clade=map(int,group_id.split('at'))
        if group_id not in groups:
            names=set()
            if genes:
                if clade not in tables:
                    table=membership_table(conn,clade)
                    # Group rows are contiguous in the original import. A gene-ID
                    # range needs scattered table reads across every ancestor level.
                    hint=lookup_index(conn,table,'cluster_id')
                    if not hint:
                        schema,table_name=table.split('.')
                        for index in conn.execute(f'PRAGMA {schema}.index_list("{table_name}")').fetchall():
                            escaped=index[1].replace('"','""');columns=conn.execute(f'PRAGMA {schema}.index_info("{escaped}")').fetchall()
                            if [c[2] for c in columns[:2]]==['clade','cluster_id']:hint=f' INDEXED BY "{escaped}"';break
                    tables[clade]=(table,hint)
                table,hint=tables[clade]
                for (gene,) in conn.execute(f'SELECT orthodb_id FROM {table}{hint} WHERE clade=? AND cluster_id=?',(clade,cluster)):
                    if gene in genes:names.update(genes[gene])
            groups[group_id]=sorted(names)
        return groups[group_id]

    return lookup


def reference_names(conn, group_id, taxid, organism_id=None):
    return reference_name_lookup(conn,taxid,organism_id)(group_id)


def identifier_column(query):
    if re.fullmatch(r'(?:\d+at\d+|ko\d{5}|K\d{5}|IPR\d+|GO:\d+)',query,re.I):return None
    return 'uniprot_id' if re.fullmatch(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})',query) else 'gene_name'


def batch_local_matches(conn, inputs, table, clade, lower, upper, limit, symbols_only=False):
    if len(inputs)>400:
        combined={}
        for start in range(0,len(inputs),400):combined.update(batch_local_matches(conn,inputs[start:start+400],table,clade,lower,upper,limit,symbols_only))
        return combined
    matches={query:[] for query in inputs}
    for column in ('gene_name','uniprot_id'):
        values=[query for query in inputs if ('gene_name' if symbols_only else identifier_column(query))==column]
        if not values:continue
        genes_hint=lookup_index(conn,'main.genes',column);member_hint=lookup_index(conn,table,'orthodb_id')
        marks=','.join('?' for _ in values)
        # Keep the indexed identifier lookup as the outer loop. Never begin with
        # a scan of every membership at the selected clade.
        sql=f'SELECT DISTINCT g.{column},m.cluster_id FROM main.genes AS g{genes_hint} CROSS JOIN {table} AS m{member_hint} WHERE g.{column} IN ({marks}) AND g.orthodb_id>=? AND g.orthodb_id<? AND m.orthodb_id=g.orthodb_id AND m.clade=?'
        for query,cluster in conn.execute(sql,[*values,lower,upper,clade]):
            if len(matches[query])<=limit:matches[query].append({'id':f'{cluster}at{clade}'})
    return matches


def choose_candidates(resolved, inputs, limit):
    valid={query:[r for r in resolved[query] if re.fullmatch(r'\d+at\d+',r.get('id','')) and r.get('public_id',r.get('id'))==r.get('id')] for query in inputs}
    # Reserve findings across inputs before adding further hits for a broad
    # query. An old alias returning hundreds must not hide later exact symbols.
    allowed=set()
    for rank in range(max((len(rows) for rows in valid.values()),default=0)):
        for query in inputs:
            if rank<len(valid[query]):allowed.add(valid[query][rank]['id'])
            if len(allowed)>=limit:break
        if len(allowed)>=limit:break
    records={}
    for query in inputs:
        for row in valid[query]:
            group=row['id']
            if group not in allowed:continue
            record=records.setdefault(group,{**row,'queries':[]})
            if query not in record['queries']:record['queries'].append(query)
    truncated=len({row['id'] for rows in valid.values() for row in rows})>limit
    return records,truncated


def resolve(request):
    tree = get_tree(request.get('treeId', '1'))
    taxid = int(request.get('taxid', 9606))
    if str(taxid) not in {s['id'] for s in leaves(tree['tree'])}:
        raise ValueError('Reference organism must belong to the selected tree')
    query_type = request.get('queryType', 'auto')
    inputs = parse_inputs(request.get('inputs', ''), query_type)
    selected=next(s for s in leaves(tree['tree']) if s['id']==str(taxid))
    organism=selected.get('organismId')
    lower=((int(organism.split('_')[0])<<32)|(int(organism.split('_')[1])<<24)) if organism else taxid<<32
    upper=lower+(1<<24 if organism else 1<<32)
    raw_limit = str(request.get('maxFindings', 100))
    if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= 2500:
        raise ValueError('Max findings must be a whole number between 1 and 2,500.')
    limit = int(raw_limit)
    candidates, unknown, warnings = {}, [], []
    name_lookup=None
    with connect(DB_PATH) as conn:
        selected_table=membership_table(conn,tree['clade'])
        emit('progress',message=f'Resolving {len(inputs)} identifiers together',current=0,total=len(inputs))
        resolved=batch_local_matches(conn,inputs,selected_table,tree['clade'],lower,upper,limit,query_type=='symbols')
        for query in inputs:
            if re.fullmatch(r'\d+at\d+',query):
                cluster,clade=map(int,query.split('at'))
                if clade!=tree['clade']:warnings.append(f'{query}: group level differs from selected tree; its membership will be filtered to that tree.')
                if conn.execute(f'SELECT 1 FROM {membership_table(conn,clade)} WHERE clade=? AND cluster_id=? LIMIT 1',(clade,cluster)).fetchone():resolved[query]=[{'id':query}]
        pending=[query for query in inputs if not resolved[query]] if query_type != 'symbols' else []
        if query_type == 'symbols':
            for query in inputs:
                if len(resolved[query]) > 1:warnings.append(f'{query}: exact symbol maps to multiple groups; all exact groups are retained.')
        if pending:
            emit('progress',message=f'{len(inputs)-len(pending)} resolved locally; looking up {len(pending)} online (up to 4 together)',current=len(inputs)-len(pending),total=len(inputs))
            outcomes={}
            with ThreadPoolExecutor(max_workers=min(4,len(pending))) as pool:
                futures={pool.submit(remote_search,query,tree['clade'],taxid,limit):query for query in pending}
                for done,future in enumerate(as_completed(futures),1):
                    query=futures[future]
                    try:outcomes[query]=future.result()
                    except (subprocess.SubprocessError,ValueError,OSError) as error:outcomes[query]=error
                    emit('progress',message=f'Identifiers resolved: {len(inputs)-len(pending)+done}/{len(inputs)}',current=len(inputs)-len(pending)+done,total=len(inputs))
            for query in pending:
                result=outcomes[query]
                if isinstance(result,Exception):warnings.append(f'{query}: online search unavailable ({type(result).__name__}).')
                else:
                    resolved[query],total=result
                    if total>len(resolved[query]):warnings.append(f'{query}: showing {len(resolved[query])} of {total} matches; increase Max findings or narrow the query.')
        unknown=[query for query in inputs if not resolved[query]]
        records,truncated=choose_candidates(resolved,inputs,limit)
        if truncated:warnings.append(f'Max findings reached ({limit}); findings are shared across input identifiers. Increase the limit or narrow broad queries for more matches.')
        if records:
            emit('progress',message='Loading reference-organism annotations')
            name_lookup=reference_name_lookup(conn,taxid,organism)
        for index,(group_id,record) in enumerate(records.items()):
            if index%25==0:emit('progress',message=f'Preparing annotations ({index}/{len(records)})',current=index,total=len(records))
            names=name_lookup(group_id)
            candidates[group_id]={'id':group_id,'name':', '.join(names[:5]) or record.get('name') or group_id,
                'genes':names,'description':record.get('name',''),'queries':record['queries'],
                'totalGenes':record.get('gene_count'),'speciesPresent':record.get('present_in')}

    return {'groups': list(candidates.values()), 'unknown': unknown, 'warnings': list(dict.fromkeys(warnings)), 'treeId': tree['id'], 'release': RELEASE, 'maxFindings': limit, 'queryType': query_type}


def build_profiles(request):
    if request.get('release', RELEASE) != RELEASE:
        raise ValueError('These matches belong to another OrthoDB release. Search again before building profiles.')
    tree = get_tree(request.get('treeId', '1'))
    species = leaves(tree['tree'])
    groups = request.get('groups', [])
    if not groups or len(groups) > 2500 or any(not re.fullmatch(r'\d+at\d+', str(g.get('id'))) for g in groups):
        raise ValueError('Choose between 1 and 2,500 valid orthogroups.')
    if len({g['id'] for g in groups}) != len(groups):
        raise ValueError('Duplicate group identifiers')
    if len(species) * len(groups) > 20_000_000:
        raise ValueError('Choose fewer groups or a smaller tree: the dataset limit is 20 million cells.')
    positions = {int(s['id']): i for i, s in enumerate(species) if s['id'].isdigit()}
    genome_positions={(int(s['organismId'].split('_')[0])<<8)|int(s['organismId'].split('_')[1]):i for i,s in enumerate(species) if s.get('organismId')}
    counts = [[0] * len(groups) for _ in species]
    start = time.monotonic()
    with connect(DB_PATH) as conn:
        for column, group in enumerate(groups):
            emit('progress', message=f'Loading {group["id"]}', current=column, total=len(groups))
            cluster, clade = map(int, group['id'].split('at'))
            table=membership_table(conn,clade)
            for (gene,) in set(conn.execute(f'SELECT orthodb_id FROM {table} WHERE clade=? AND cluster_id=?', (clade, cluster))):
                if genome_positions:
                    row=genome_positions.get(gene>>24)
                else:
                    row=positions.get(TRANSLATION.get(gene >> 32, gene >> 32))
                if row is not None:counts[row][column] += 1
    stat = DB_PATH.stat()
    return {'schemaVersion': 1, 'title': request.get('title', 'Phylogenetic profile'), 'tree': tree['tree'],
        'species': species, 'groups': groups, 'counts': counts, 'source': {'provider': 'OrthoDB', 'release': RELEASE,
        'tree': tree['name'], 'treeId': tree['id'], 'treeKind':tree.get('treeKind','Curated topology'), 'representativePolicy':tree.get('representativePolicy'), 'availableGenomes':tree.get('genomeCount'), 'ncbiTaxonomySource':tree.get('ncbiSource'), 'timetreeSource':tree.get('timetreeSource'), 'branchLengths':tree.get('branchLengths',False), 'branchLengthUnit':tree.get('branchLengthUnit'), 'rootAgeMyr':tree.get('rootAgeMyr'), 'coverage':tree.get('coverage'), 'query': request.get('inputs', ''), 'databaseFingerprint': hashlib.sha256(f'{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()[:16],
        'seconds': round(time.monotonic()-start, 3), 'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'notes': ['Species follow the NCBI parent hierarchy and merged-taxid mapping when an NCBI snapshot is recorded; sibling clades are ordered by scientific name. Unresolved taxa are marked explicitly. Branches do not imply evolutionary distances.', 'v13 species rows use one representative clustered genome per current NCBI species, preventing alternate assemblies from inflating copy counts.', 'Counts are distinct genes from the selected representative organism IDs; alternate assemblies are excluded.' if genome_positions else 'Counts are distinct legacy-compatible genes filtered to the selected tree; historical taxonomy aliases are retained.']}}


def panther(request):
    query = str(request.get('gene', '')).strip()
    if not query or len(query) > 150:
        raise ValueError('Choose a valid gene or UniProt identifier')
    reference = panther_reference()
    tree, mapping = reference['tree'], reference['mapping']
    taxid = str(request.get('taxid', 9606))
    genome = next((code for code, value in mapping.items() if value == taxid), None)
    accession = bool(re.fullmatch(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})', query))
    with connect(reference['database']) as conn:
        scope, parameters = (' AND Genome=?', [genome]) if genome else ('', [])
        if accession and reference['release'] == 'v19':
            # v19 has a UniProt index; do not round-trip through older OrthoDB names.
            families = [r[0] for r in conn.execute('SELECT DISTINCT PantherID FROM panther WHERE Uniprot=?' + scope + ' LIMIT 11', [query, *parameters])]
        else:
            symbols = [query]
            if accession:
                with connect(DB_PATH) as orthodb:
                    symbols = sorted({part.strip() for (name,) in orthodb.execute('SELECT gene_name FROM genes WHERE uniprot_id=? LIMIT 100', (query,)) if name for part in name.split(';') if part.strip()})[:20]
                if not symbols:
                    raise ValueError('No local gene-name mapping for this UniProt ID; use a gene symbol for PANTHER.')
            marks = ','.join('?' for _ in symbols)
            families = [r[0] for r in conn.execute('SELECT DISTINCT PantherID FROM panther WHERE Gene IN (' + marks + ') AND PantherID IS NOT NULL' + scope + ' LIMIT 11', [*symbols, *parameters])]
        families = [family for family in families if family]
        if not families:
            raise ValueError('No PANTHER family found for this identifier in the local database.')
        if len(families) > 10:
            raise ValueError('Identifier matches more than ten PANTHER families; choose a specific UniProt accession or reference organism.')
        chosen = request.get('family') or (families[0] if len(families) == 1 else None)
        if chosen not in families:
            if not request.get('family'):
                return {'familyOptions': [{'id': family} for family in families], 'gene': query}
            raise ValueError('Selected PANTHER family does not match this identifier.')
        has_ids = 'PantherID_2nd_half' in {row[1] for row in conn.execute('PRAGMA table_info(panther)')}
        id_field = 'PantherID_2nd_half' if has_ids else 'NULL'
        records = conn.execute('SELECT Genome,Uniprot,Family,Subfamily,' + id_field + ' FROM panther WHERE PantherID=?', (chosen,)).fetchall()
    # Group by the supplied NAME, even when multiple SF IDs share that name.
    # Keep rare and unnamed assignments rather than silently filtering them out.
    bins = {}
    for record_genome, uniprot, family, name, sub_id in records:
        key = str(name).strip() if name and str(name).strip() else None
        entry = bins.setdefault(key, {'proteins': set(), 'ids': set()})
        entry['proteins'].add((record_genome, uniprot))
        if sub_id and str(sub_id).strip():entry['ids'].add(str(sub_id).strip())
    names = sorted((name for name in bins if name is not None), key=str.casefold)
    if None in bins:names.append(None)
    if len(names) > 2500:raise ValueError('This family exceeds the viewer limit of 2,500 named subfamilies.')
    species = leaves(tree['tree']); positions = {s['id']: i for i, s in enumerate(species)}
    counts = [[0]*len(names) for _ in species];groups=[]
    family_name = next((str(row[2]).strip() for row in records if row[2]), chosen)
    for column, name in enumerate(names):
        entry = bins[name]
        for record_genome, uniprot in entry['proteins']:
            species_id = mapping.get(record_genome)
            if species_id in positions:counts[positions[species_id]][column] += 1
        label = name if name is not None else 'Unassigned subfamily'
        groups.append({'id': f'{chosen}:name:{label}', 'name': label, 'familyId': chosen,
                       'subfamilyIds': sorted(entry['ids']), 'proteinCount': len(entry['proteins']),
                       'unassigned': name is None, 'description': family_name if name is not None else family_name + ' · no subfamily name supplied', 'genes': []})
    return {'schemaVersion': 1, 'title': f'PANTHER subfamilies · {query}', 'tree': tree['tree'], 'species': species,
            'groups': groups, 'counts': counts, 'source': {'provider': 'PANTHER', 'release': reference['release'],
            'query': query, 'familyId': chosen, 'familyName': family_name, 'grouping': 'subfamily_name', 'minimumSupport': 1,
            'referenceTaxid': taxid, 'notes': ['Each column is a distinct supplied subfamily name across the entire PANTHER family; paralogous subfamilies are included.',
            'Multiple SF IDs with the same name share one column. Rare subfamilies are retained; no minimum-nine-record filter is applied.',
            'Counts are distinct UniProt protein accessions per genome and subfamily name; presence view converts any positive count to 1.',
            'Records without a subfamily name appear in an explicitly unassigned column.']}}


def panther_orthologs(request):
    reference = panther_reference()
    if reference['release'] != 'v19' or not reference['relationships']:
        raise ValueError('PANTHER v19 ortholog data is still being prepared. Subfamily profiles remain available.')
    query = str(request.get('gene', '')).strip()
    taxid = str(request.get('taxid', '9606'))
    if not query or len(query) > 150:
        raise ValueError('Choose a valid gene or UniProt identifier')
    genome = next((code for code, value in reference['mapping'].items() if value == taxid), None)
    if not genome:
        raise ValueError('The reference organism is not represented in the PANTHER v19 tree')
    mode = request.get('mode', 'ldo')
    if mode not in ('ldo', 'all'):
        raise ValueError('Choose least-diverged or all orthologs')
    kinds = ('LDO',) if mode == 'ldo' else ('LDO', 'O')
    with connect(reference['database']) as db:
        seeds = db.execute('SELECT DISTINCT Uniprot,Gene FROM panther WHERE Genome=? AND Gene=? LIMIT 21', (genome, query)).fetchall()
        if not seeds:
            seeds = db.execute('SELECT DISTINCT Uniprot,Gene FROM panther WHERE Genome=? AND Uniprot=? LIMIT 21', (genome, query)).fetchall()
    if not seeds:
        raise ValueError('No matching v19 gene in the chosen reference organism')
    if len(seeds) > 20:
        raise ValueError('This gene name matches more than 20 proteins; use a specific UniProt accession')
    species = leaves(reference['tree']['tree'])
    positions = {row['id']: i for i, row in enumerate(species)}
    counts = [[0] * len(seeds) for _ in species]
    groups = []
    with connect(reference['relationships']) as db:
        for column, (accession, symbol) in enumerate(seeds):
            source = db.execute('SELECT gene_id FROM genes WHERE canonical_key=?', (genome + '|' + accession,)).fetchone()
            if not source:
                raise ValueError('Reference gene has no v19 relationship identifier')
            marks = ','.join('?' for _ in kinds)
            neighbors = db.execute(f'''SELECT DISTINCT g.genome,g.uniprot FROM
              (SELECT gene_b AS target FROM relationships WHERE gene_a=? AND relation IN ({marks})
               UNION ALL SELECT gene_a FROM relationships WHERE gene_b=? AND relation IN ({marks})) r
              JOIN genes g ON g.gene_id=r.target''', [source[0], *kinds, source[0], *kinds]).fetchall()
            for target_genome, target_accession in neighbors:
                target_taxid = reference['mapping'].get(target_genome)
                if target_taxid in positions:
                    counts[positions[target_taxid]][column] += 1
            # Reference-species cell marks the input gene, not a self-orthology claim.
            counts[positions[taxid]][column] = 1
            groups.append({'id': f'PANTHER19:{genome}:{accession}:{mode}', 'name': f'{symbol or accession} · {"LDO" if mode == "ldo" else "LDO + O"}', 'genes': [], 'description': f'Direct v19 orthologs of {genome}/{accession}; paralogs excluded'})
    return {'schemaVersion': 1, 'title': f'PANTHER orthologs · {query}', 'tree': reference['tree']['tree'], 'species': species, 'groups': groups, 'counts': counts,
            'source': {'provider': 'PANTHER orthologs', 'release': 'v19', 'query': query, 'referenceGenome': genome, 'relationTypes': list(kinds),
            'notes': ['Only reported direct LDO/O edges are counted, not shared-family membership or inferred transitive links.', 'Targets are distinct by genome and UniProt ID; P (paralog) edges are excluded.', 'The reference-species cell marks the query gene itself; it is not a self-orthology assertion.']}}


if __name__ == '__main__':
    try:
        request = json.loads(sys.stdin.read(10_000_001))
        handler = {'config': config, 'resolve': resolve, 'profiles': build_profiles, 'panther': panther, 'panther_orthologs': panther_orthologs}.get(request.pop('action', ''))
        if handler is None:
            raise ValueError('Unknown action')
        emit('result', data=handler() if handler is config else handler(request))
    except Exception as error:
        emit('error', message=str(error) if not isinstance(error, sqlite3.OperationalError) else 'Database read failed or exceeded the 120-second per-query budget: ' + str(error))
        sys.exit(1)
