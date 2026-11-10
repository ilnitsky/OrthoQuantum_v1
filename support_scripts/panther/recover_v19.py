#!/usr/bin/env python3
"""Rebuild interrupted relationships, preserving the original staging bundle."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time

from build_v19 import GIB, HUMAN, build_relationships, sha256
from tree_assets import write_assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--streamer', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / 'panther_v19'
    previous = root / 'panther_v19.building'
    downloads = root / 'panther_v19_downloads'
    report_path = root / 'panther_v19.build.json'
    with (downloads / 'build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if output.exists():
            raise RuntimeError('Published output already exists')
        report = json.loads(report_path.read_text())
        if report['release'] != 'PANTHER19.0' or not report.get('classification'):
            raise RuntimeError('No completed v19 classification checkpoint')
        staging = root / ('panther_v19.recovery-' + str(time.time_ns()))

        def progress(message):
            report.update(message=message, updated_unix=int(time.time()))
            temp = Path(str(report_path) + '.tmp')
            temp.write_text(json.dumps(report, indent=2) + '\n')
            temp.replace(report_path)
            print(message, flush=True)

        try:
            report.update(status='building', phase='recovery_validation',
                          recovery_started_unix=int(time.time()), recovery_staging=str(staging))
            progress('Verifying all downloaded source hashes before recovery')
            for name, metadata in report['files'].items():
                path = downloads / name
                if path.stat().st_size != metadata['bytes'] or sha256(path) != metadata['sha256']:
                    raise RuntimeError('Source checksum mismatch: ' + name)
            if shutil.disk_usage(root).free < 24 * GIB:
                raise RuntimeError('Require 24 GiB free for relationship recovery')
            staging.mkdir()
            (staging / 'tmp').mkdir()
            os.environ['SQLITE_TMPDIR'] = str(staging / 'tmp')
            species = write_assets(downloads / 'species_list.tsv', downloads / 'species_pthr19_annot.nhx', staging)
            source = previous / 'panther.sqlite'
            with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as db:
                if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise RuntimeError('Classification checkpoint failed quick_check')
                if db.execute('SELECT count(*) FROM panther').fetchone()[0] != report['classification']['rows']:
                    raise RuntimeError('Classification checkpoint count mismatch')
                if {r[0] for r in db.execute('SELECT DISTINCT Genome FROM panther')} != set(species):
                    raise RuntimeError('Classification checkpoint species mismatch')
                for acc, symbol in HUMAN.items():
                    if not db.execute('SELECT 1 FROM panther WHERE Genome=? AND Uniprot=? AND Gene=?', ('HUMAN', acc, symbol)).fetchone():
                        raise RuntimeError('Classification checkpoint missing ' + acc)
            shutil.copyfile(source, staging / 'panther.sqlite')
            report['phase'] = 'relationships'
            report['relationships'] = build_relationships(
                staging / 'relationships.sqlite', staging / 'panther.sqlite',
                downloads, args.streamer, progress, species)
            for name in ('species_list.tsv', 'species_pthr19_annot.nhx'):
                shutil.copyfile(downloads / name, staging / name)
            report.update(status='complete', phase='validated', species=len(species),
                          seconds=int(time.time()) - report['started_unix'])
            (staging / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
            for name in ('panther.sqlite', 'relationships.sqlite', 'manifest.json'):
                with (staging / name).open('rb') as completed:
                    os.fsync(completed.fileno())
            if output.exists():
                raise RuntimeError('Output appeared; refusing replacement')
            staging.rename(output)
            progress('Published validated PANTHER v19 bundle; live DB unchanged')
        except BaseException as error:
            report.update(status='failed', error=str(error))
            progress('PANTHER recovery stopped: ' + str(error))
            raise


if __name__ == '__main__':
    main()
