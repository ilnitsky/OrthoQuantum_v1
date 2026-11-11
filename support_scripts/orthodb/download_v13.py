#!/usr/bin/env python3
"""Download the tables needed for OrthoQuantum's v13 database preparation.

No extraction, database replacement, cache clearing, or application migration.
Downloads resume from .part files; completed files must match upstream MD5.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time

BASE = 'https://data.orthodb.org/v13/download/odb_data_dump/'
# Official index: checked against the upstream listing before downloading.
FILES = {
    'README.txt': 'ef566ab09cd88d0bb6ba33ec87ab5318',
    'odb13v0_levels.tab.gz': 'ac4b09d17eb004448fcb143795f94b85',
    'odb13v0_species.tab.gz': '3ff52b9ca398d5749c248c617be353a6',
    'odb13v0_level2species.tab.gz': '252399ef8a288daf9a7714bc0342b2f6',
    'odb13v0_OGs.tab.gz': '6776f23fa1521ab0c7511c0dd355a21f',
    'odb13v0_genes.tab.gz': '73bb14e572ca03096bf72057c9ac92a5',
    'odb13v0_gene_xrefs.tab.gz': '19c57406d3b4c20018ea6abd823c6eae',
    'odb13v0_OG2genes.tab.gz': '2ac5620628353b74a2a27a6fe5dc0ae1',
}


def md5(path):
    digest = hashlib.md5()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--proxy', default='socks5h://127.0.0.1:10808')
    parser.add_argument('--jobs', type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # One process per destination; OS releases this lock after interruptions.
    import fcntl
    lock_file = (root / '.download.lock').open('a')
    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    completed_bytes = sum((root / name).stat().st_size for name in FILES if (root / name).exists())
    partial_bytes = sum((root / (name + '.part')).stat().st_size for name in FILES if (root / (name + '.part')).exists())
    remaining = max(0, 14_000_000_000 - completed_bytes - partial_bytes)
    if shutil.disk_usage(root).free < remaining + 5_000_000_000:
        raise RuntimeError('Not enough free space for remaining compressed files plus 5 GB reserve')

    state = {'release': 'odb13v0', 'source': BASE, 'status': 'downloading', 'files': {}}
    state_lock = threading.Lock()

    def update(name, **values):
        with state_lock:
            state['files'].setdefault(name, {'expected_md5': FILES[name]}).update(values)
            save()

    def save():
        state['updated_unix'] = int(time.time())
        tmp = root / 'download-status.json.tmp'
        tmp.write_text(json.dumps(state, indent=2) + '\n')
        tmp.replace(root / 'download-status.json')

    def download(name, expected):
        final = root / name
        part = root / (name + '.part')
        try:
            if not final.exists():
                update(name, status='downloading')
                print(f'Downloading {name}', flush=True)
                subprocess.run([
                    'curl', '--fail', '--location', '--silent', '--show-error',
                    '--retry', '8', '--retry-all-errors', '--retry-delay', '10',
                    '--connect-timeout', '20', '--speed-time', '90', '--speed-limit', '1024',
                    '--proxy', args.proxy, '--continue-at', '-', '--output', str(part), BASE + name,
                ], check=True)
                candidate = part
            else:
                candidate = final
            update(name, status='verifying')
            actual = md5(candidate)
            if actual != expected:
                raise RuntimeError(f'{name}: MD5 mismatch: expected {expected}, received {actual}; file retained for inspection')
            columns = None
            if name.endswith('.gz'):
                with gzip.open(candidate, 'rt', encoding='utf-8') as stream:
                    columns = len(stream.readline().rstrip('\r\n').split('\t'))
            if candidate == part:
                part.replace(final)
            update(name, status='verified', md5=actual, bytes=final.stat().st_size, first_row_columns=columns)
            print(f'Verified {name}: {final.stat().st_size:,} bytes, MD5 {actual}', flush=True)
        except Exception as exc:
            update(name, status='failed', error=str(exc))
            raise

    errors = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = {pool.submit(download, name, digest) for name, digest in FILES.items()}
        while pending:
            finished, pending = wait(pending, timeout=30)
            for future in finished:
                try:
                    future.result()
                except Exception as exc:
                    errors.append(str(exc))
            size = 0
            for path in root.glob('*.part'):
                try:
                    size += path.stat().st_size
                except FileNotFoundError:
                    pass  # A verified download was just renamed.
            print(f'Progress: {len(pending)} jobs remaining; {size / 2**30:.2f} GiB in partial files', flush=True)
    state['status'] = 'failed' if errors else 'complete'
    save()
    if errors:
        raise RuntimeError('\n'.join(errors))
    print('All required v13 downloads verified. Live application/database unchanged.', flush=True)


if __name__ == '__main__':
    main()
