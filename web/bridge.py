"""Isolated, read-only SQLite adapter. NDJSON progress in; no Dash/Redis imports."""
import csv
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

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'public/data'
TREES = json.loads((DATA / 'trees.json').read_text())
DB_PATH = Path(os.environ.get('ORTHODB_PATH', '/home/ilnitsky/PANTHERDB/orthodb.db'))
PANTHER_PATH = Path(os.environ.get('PANTHER_PATH', '/home/ilnitsky/PANTHERDB/panther.sqlite'))
RELEASE = os.environ.get('ORTHODB_RELEASE', 'v11')
COMMON = (9606, 10090, 7955, 7227, 6239, 10116, 9031, 8364, 4932, 3702)
TRANSLATION = {441894:8801,381198:8845,216574:8962,74533:9694,62698:9708,310752:9767,127582:9778,73337:9807,1230840:9818,43346:9901,299123:40157,556262:100884,319938:288004,1841481:302047,1505932:408180,595593:656366,667632:863227,1336249:1367849,1220582:1368415,1834200:1796646,1166016:1905730}


def emit(kind, **values):
    print(json.dumps({'type': kind, **values}, separators=(',', ':')), flush=True)


def leaves(node):
    if not node.get('children'):
        return [{'id': str(node['id']), 'name': node['name']}] if node.get('id') else []
    return [leaf for child in node['children'] for leaf in leaves(child)]


def get_tree(tree_id):
    tree = next((t for t in TREES if t['id'] == str(tree_id)), None)
    if tree is None:
        raise ValueError('Unknown tree selection')
    return tree


def connect(path):
    if not path.is_file():
        raise ValueError(f'Reference database is unavailable: {path.name}. Bundled demos and file import still work.')
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    conn.execute('PRAGMA query_only=ON')
    conn.execute('PRAGMA cache_size=-16384')
    deadline = time.monotonic() + 120
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    return conn


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
    result = []
    for tree in TREES:
        if tree['id'] == 'panther':
            continue
        species = [s for s in leaves(tree['tree']) if s['id'].isdigit()]
        species.sort(key=lambda s: (COMMON.index(int(s['id'])) if s['id'].isdigit() and int(s['id']) in COMMON else len(COMMON), s['name'].lower()))
        result.append({'id': tree['id'], 'name': tree['name'], 'clade': tree['clade'], 'species': species})
    reference = panther_reference()
    return {'trees': result, 'databaseAvailable': DB_PATH.is_file(), 'pantherAvailable': reference['database'].is_file(), 'pantherRelease': reference['release'], 'pantherOrthologsAvailable': bool(reference['relationships'] and reference['relationships'].is_file()), 'release': RELEASE}


def remote_search(query, clade, taxid):
    # Hostnames/paths are fixed. Inputs enter only URL-encoded query parameters.
    if not re.fullmatch(r'v\d+', RELEASE):
        raise ValueError('Invalid configured OrthoDB release')
    url = f'https://data.orthodb.org/{RELEASE}/search?' + urllib.parse.urlencode({'query': query, 'level': clade, 'species': taxid, 'take': 100})
    command = ['curl', '--fail', '--silent', '--show-error', '--max-time', '25', '--max-filesize', '4000000']
    proxy = os.environ.get('ORTHODB_PROXY', '')
    if proxy:
        command += ['--proxy', proxy]
    raw = subprocess.run(command + [url], capture_output=True, timeout=30, check=True).stdout
    data = json.loads(raw)
    if data.get('status') != 'ok':
        raise ValueError('OrthoDB search did not return a successful response')
    return data.get('bigdata') or [], int(data.get('count') or 0)


def reference_names(conn, group_id, taxid):
    cluster, clade = map(int, group_id.split('at'))
    ids = sorted({g for (g,) in conn.execute('SELECT orthodb_id FROM orthodb_to_og WHERE clade=? AND cluster_id=?', (clade, cluster)) if g >> 32 == taxid})
    names = set()
    for start in range(0, len(ids), 500):
        batch = ids[start:start + 500]
        names.update(name for (name,) in conn.execute('SELECT gene_name FROM genes WHERE orthodb_id IN (' + ','.join('?' for _ in batch) + ')', batch) if name)
    # Split legacy synonyms so individual PANTHER gene links remain usable.
    return sorted({part.strip() for name in names for part in name.split(';') if part.strip()})


def resolve(request):
    tree = get_tree(request.get('treeId', '1'))
    taxid = int(request.get('taxid', 9606))
    if str(taxid) not in {s['id'] for s in leaves(tree['tree'])}:
        raise ValueError('Reference organism must belong to the selected tree')
    inputs = list(dict.fromkeys(v.strip() for v in str(request.get('inputs', '')).splitlines() if v.strip() and not v.lstrip().startswith('#')))
    if not inputs or len(inputs) > 50 or any(len(q) > 150 for q in inputs):
        raise ValueError('Enter 1–50 identifiers, one per line (maximum 150 characters each).')
    candidates, unknown, warnings = {}, [], []
    with connect(DB_PATH) as conn:
        for i, query in enumerate(inputs):
            emit('progress', message=f'Resolving {query}', current=i, total=len(inputs))
            records = []
            if re.fullmatch(r'\d+at\d+', query):
                cluster, clade = map(int, query.split('at'))
                if clade != tree['clade']:
                    warnings.append(f'{query}: group level differs from selected tree; its membership will be filtered to that tree.')
                if conn.execute('SELECT 1 FROM orthodb_to_og WHERE clade=? AND cluster_id=? LIMIT 1', (clade, cluster)).fetchone():
                    records = [{'id': query}]
            elif not re.fullmatch(r'(?:ko\d{5}|K\d{5}|IPR\d+)', query, re.I):
                column = 'uniprot_id' if re.fullmatch(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})', query) else 'gene_name'
                local = conn.execute(f'SELECT DISTINCT m.cluster_id FROM genes g JOIN orthodb_to_og m USING(orthodb_id) WHERE g.{column}=? AND g.orthodb_id>=? AND g.orthodb_id<? AND m.clade=? LIMIT 101', (query, taxid << 32, (taxid+1) << 32, tree['clade'])).fetchall()
                records = [{'id': f'{cluster}at{tree["clade"]}'} for (cluster,) in local]
            if not records:
                try:
                    records, total = remote_search(query, tree['clade'], taxid)
                    if total > len(records):
                        warnings.append(f'{query}: showing {len(records)} of {total} matches; narrow the query if needed.')
                except (subprocess.SubprocessError, ValueError, OSError) as error:
                    warnings.append(f'{query}: online search unavailable ({type(error).__name__}).')
            if not records:
                unknown.append(query)
            for record in records:
                group_id = record.get('id', '')
                if not re.fullmatch(r'\d+at\d+', group_id) or record.get('public_id', group_id) != group_id:
                    continue
                if len(candidates) >= 100 and group_id not in candidates:
                    warnings.append('Candidate limit is 100 groups. Narrow the input for further matches.')
                    break
                if group_id in candidates:
                    candidates[group_id]['queries'].append(query)
                    continue
                names = reference_names(conn, group_id, taxid)
                candidates[group_id] = {'id': group_id, 'name': ', '.join(names[:5]) or record.get('name') or group_id,
                    'genes': names, 'description': record.get('name', ''), 'queries': [query],
                    'totalGenes': record.get('gene_count'), 'speciesPresent': record.get('present_in')}
    return {'groups': list(candidates.values()), 'unknown': unknown, 'warnings': list(dict.fromkeys(warnings)), 'treeId': tree['id'], 'release': RELEASE}


def build_profiles(request):
    tree = get_tree(request.get('treeId', '1'))
    species = leaves(tree['tree'])
    groups = request.get('groups', [])
    if not groups or len(groups) > 200 or any(not re.fullmatch(r'\d+at\d+', str(g.get('id'))) for g in groups):
        raise ValueError('Choose between 1 and 200 valid orthogroups.')
    if len({g['id'] for g in groups}) != len(groups):
        raise ValueError('Duplicate group identifiers')
    positions = {int(s['id']): i for i, s in enumerate(species) if s['id'].isdigit()}
    counts = [[0] * len(groups) for _ in species]
    start = time.monotonic()
    with connect(DB_PATH) as conn:
        for column, group in enumerate(groups):
            emit('progress', message=f'Loading {group["id"]}', current=column, total=len(groups))
            cluster, clade = map(int, group['id'].split('at'))
            for (gene,) in set(conn.execute('SELECT orthodb_id FROM orthodb_to_og WHERE clade=? AND cluster_id=?', (clade, cluster))):
                taxid = TRANSLATION.get(gene >> 32, gene >> 32)
                if taxid in positions:
                    counts[positions[taxid]][column] += 1
    stat = DB_PATH.stat()
    return {'schemaVersion': 1, 'title': request.get('title', 'Phylogenetic profile'), 'tree': tree['tree'],
        'species': species, 'groups': groups, 'counts': counts, 'source': {'provider': 'OrthoDB', 'release': RELEASE,
        'tree': tree['name'], 'treeId': tree['id'], 'query': request.get('inputs', ''), 'databaseFingerprint': hashlib.sha256(f'{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()[:16],
        'seconds': round(time.monotonic()-start, 3), 'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'notes': ['Counts are distinct legacy-compatible genes, filtered to the selected tree. Species aliases follow the production mapping. Gene-name hover lists are omitted to avoid expensive annotation joins.']}}


def panther(request):
    query = str(request.get('gene', '')).strip()
    if not query or len(query) > 150:
        raise ValueError('Choose a valid gene or UniProt identifier')
    reference = panther_reference()
    tree, mapping = reference['tree'], reference['mapping']
    with connect(reference['database']) as conn:
        # Only Gene and PantherID are indexed in the legacy PANTHER DB.
        # OR-ing Gene with unindexed Uniprot forces a multi-GB table scan.
        symbols = [query]
        if re.fullmatch(r'(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})', query):
            with connect(DB_PATH) as orthodb:
                symbols = sorted({part.strip() for (name,) in orthodb.execute(
                    'SELECT gene_name FROM genes WHERE uniprot_id=? LIMIT 100', (query,)) if name
                    for part in name.split(';') if part.strip()})[:20]
            if not symbols:
                raise ValueError('No local gene-name mapping for this UniProt ID; use a gene symbol for PANTHER.')
        marks = ','.join('?' for _ in symbols)
        families = [r[0] for r in conn.execute('SELECT DISTINCT PantherID FROM panther WHERE Gene IN (' + marks + ') AND PantherID IS NOT NULL LIMIT 11', symbols)]
        if not families:
            raise ValueError('No PANTHER family found for this identifier in the local database.')
        chosen = request.get('family') or (families[0] if len(families) == 1 else None)
        if chosen not in families:
            if not request.get('family'):
                return {'familyOptions': [{'id': family} for family in families], 'gene': query}
            raise ValueError('Selected PANTHER family does not match this identifier.')
        records = conn.execute('SELECT Genome,Gene,Family,Subfamily FROM panther WHERE PantherID=?', (chosen,)).fetchall()
    # Match the existing app: retain subfamilies represented by more than 8 records.
    support = {}
    for genome, gene, family, subfamily in records:
        if subfamily:
            support[subfamily] = support.get(subfamily, 0) + 1
    subfamilies = sorted(s for s, n in support.items() if n > 8)
    if not subfamilies:
        raise ValueError('No subfamilies meet the existing minimum support of 9 records.')
    if len(subfamilies) > 200:
        raise ValueError('This family exceeds the prototype limit of 200 subfamilies.')
    species = leaves(tree['tree']); positions = {s['id']: i for i, s in enumerate(species)}
    columns = {s: i for i, s in enumerate(subfamilies)}; counts = [[0]*len(columns) for _ in species]
    for genome, gene, family, subfamily in records:
        taxid = mapping.get(genome)
        if taxid in positions and subfamily in columns:
            counts[positions[taxid]][columns[subfamily]] = 1
    return {'schemaVersion': 1, 'title': f'PANTHER · {query}', 'tree': tree['tree'], 'species': species,
        'groups': [{'id': f'{chosen}:{s}', 'name': s, 'description': records[0][2], 'genes': []} for s in subfamilies], 'counts': counts,
        'source': {'provider': 'PANTHER', 'release': reference['release'], 'query': query,
        'notes': ['Subfamilies require at least 9 records, matching the existing app. Presence is binary per genome/subfamily. Local PANTHER release provenance is unspecified.']}}


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
        request = json.loads(sys.stdin.read(1000000))
        handler = {'config': config, 'resolve': resolve, 'profiles': build_profiles, 'panther': panther, 'panther_orthologs': panther_orthologs}.get(request.pop('action', ''))
        if handler is None:
            raise ValueError('Unknown action')
        emit('result', data=handler() if handler is config else handler(request))
    except Exception as error:
        emit('error', message=str(error) if not isinstance(error, sqlite3.OperationalError) else 'Database read failed or exceeded the 120-second query budget: ' + str(error))
        sys.exit(1)
