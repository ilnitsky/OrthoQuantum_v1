"""Version-matched group annotations; IDs must never cross OrthoDB releases."""
import re
import time

API_BASE = 'https://data.orthodb.org/v11'
CACHE_PREFIX = '/cache/ortho/v11-group'
GROUP_ID = re.compile(r'\d+at\d+\Z')


def parse_group(group_id, payload, fields):
    if payload.get('status') != 'ok' or not isinstance(payload.get('data'), dict):
        raise ValueError('OrthoDB did not return group data')
    data = payload['data']
    if group_id not in (data.get('id'), data.get('public_id')):
        raise ValueError('OrthoDB returned a different group ID')
    profile = data.get('phyletic_profile') or {}
    architecture = data.get('gene_architecture') or {}
    values = {
        'label': group_id,
        'og': f'http://purl.orthodb.org/odbgroup/{group_id}',
        'description': data.get('name'), 'clade': data.get('level_name'),
        'evolRate': data.get('evolutionary_rate'),
        'totalGenesCount': profile.get('gene_count'),
        # These are counts of species with single/multiple copies, not gene counts.
        'multiCopyGenesCount': profile.get('multi_copy'),
        'singleCopyGenesCount': profile.get('single_copy'),
        'inSpeciesCount': profile.get('present_in'),
        'medianProteinLength': architecture.get('protein_median_length'),
        'stddevProteinLength': architecture.get('protein_stdev_length'),
    }
    # Redis hashes cannot store None. Empty strings mean unavailable, never zero.
    return {field: '' if values.get(field) is None else str(values[field]).strip() for field in fields}


def fetch_group_metadata(requested_ids, fields):
    import requests
    result = {}
    with requests.Session() as session:
        for group_id in requested_ids:
            if not GROUP_ID.fullmatch(group_id):
                raise ValueError(f'Invalid OrthoDB group: {group_id}')
            for attempt in range(3):
                try:
                    response = session.get(f'{API_BASE}/group', params={'id': group_id}, timeout=(10, 30))
                    response.raise_for_status()
                    result[group_id] = parse_group(group_id, response.json(), fields)
                    break
                except (requests.RequestException, ValueError) as exc:
                    if attempt == 2:
                        print(f'OrthoDB v11 metadata unavailable for {group_id}: {exc}', flush=True)
                        result[group_id] = None
                    else:
                        time.sleep(0.5 * (attempt + 1))
    return result
