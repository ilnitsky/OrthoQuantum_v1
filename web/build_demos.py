"""Rebuild bundled real-data demos using a read-only v11-compatible reference."""
import json
from pathlib import Path
import bridge

ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    if bridge.RELEASE != 'v11':
        raise SystemExit('These saved group IDs are v11; do not reuse them with another release.')
    seeds = json.loads((bridge.DATA / 'demo-seeds.json').read_text())
    for seed in seeds:
        groups = seed['groups']
        if seed['kind'] == 'interpro':
            with bridge.connect(bridge.DB_PATH) as connection:
                for group in groups:
                    group['genes'] = bridge.reference_names(connection, group['id'], 9606)
                    group['name'] = ', '.join(group['genes'][:5]) or group['description'] or group['id']
        result = bridge.build_profiles({'treeId':seed['treeId'],'groups':groups,'inputs':seed['query'],'title':seed['title']})
        result['source'].update(sampleId='demo-'+seed['kind'],treeId=seed['treeId'],notes=result['source']['notes']+[seed['note'], 'Tree leaves with nonnumeric historical IDs have no local taxid mapping and retain zero findings.'])
        target = bridge.DATA / ('demo-'+seed['kind']+'.json')
        target.write_text(json.dumps(result,separators=(',',':')))
        print(f'Wrote {target.name}: {len(result["species"])} species × {len(groups)} groups',flush=True)
