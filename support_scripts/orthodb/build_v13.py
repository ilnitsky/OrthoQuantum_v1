#!/usr/bin/env python3
"""Build a separate v13 SQLite database using the live database's exact schema."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Existing schema reference, opened read-only')
    parser.add_argument('--archives', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--streamer', type=Path, required=True)
    parser.add_argument('--resume-genes', action='store_true', help='Recover a cleanly failed gene-ingestion stage after SQLite validation')
    parser.add_argument('--resume-validation', action='store_true', help='Continue a terminated read-only recovery validation, before ingestion restarted')
    args = parser.parse_args()
    if args.resume_validation:
        args.resume_genes = True
    source, output = args.source.resolve(), args.output.resolve()
    staging = output.with_name(output.name + '.building')
    if source == output or source == staging:
        raise RuntimeError('Output must be separate from live database')
    if output.exists() or (staging.exists() and not args.resume_genes):
        raise RuntimeError('Output/staging already exists; refusing to overwrite or reuse an interrupted build')
    previous = None
    if args.resume_genes:
        previous = json.loads(output.with_name(output.name + '.build.json').read_text())
        validating = args.resume_validation and previous['status'] == 'building' and not previous['stages']
        clean_failure = previous['status'] == 'failed' and set(previous['stages']) == {'genes'} and previous.get('error') == 'Malformed streamer output for genes'
        if not staging.exists() or not (validating or clean_failure):
            raise RuntimeError('Resume is limited to the known failed gene load or its terminated read-only validation')
    status = json.loads((args.archives / 'download-status.json').read_text())
    for name in ('odb13v0_genes.tab.gz', 'odb13v0_OG2genes.tab.gz', 'odb13v0_levels.tab.gz'):
        info = status['files'][name]
        if status['release'] != 'odb13v0' or info['status'] != 'verified' or info['md5'] != info['expected_md5']:
            raise RuntimeError(f'Unverified input: {name}')
        if (args.archives / name).stat().st_size != info['bytes']:
            raise RuntimeError(f'Input size changed: {name}')
    if shutil.disk_usage(output.parent).free < 60 * 2**30:
        raise RuntimeError('Require at least 60 GiB free for database and temporary indexes')
    ref = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    schema = ref.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC,name").fetchall()
    tables = {name for kind, name, _ in schema if kind == 'table'}
    if tables != {'genes', 'orthodb_to_og', 'levels'}:
        raise RuntimeError(f'Unexpected reference schema: {tables}')
    levels = ref.execute('SELECT level_id,scientific_name FROM levels').fetchall()
    level_arg = ','.join(str(level) for level, _ in levels)
    with gzip.open(args.archives / 'odb13v0_levels.tab.gz', 'rt') as f:
        official = {int(row.split('\t')[0]): row.split('\t')[1] for row in f}
    report = {
        'release': 'odb13v0', 'source_schema': str(source), 'output': str(output),
        'started_unix': int(time.time()), 'status': 'building', 'stages': {},
        'missing_v13_levels': [[i, name] for i, name in levels if i not in official],
        'gene_mapping': 'v13 genes columns 1, 5 (split UniProt mappings), 7; empty mappings become NULL; rows with neither mapping omitted',
        'levels_policy': 'Retain reference level IDs/names, including historical/custom levels',
        'mapped_only_policy': 'Exclude u_ mapped-only identifiers: legacy 32/8/24-bit encoding cannot represent them; matches legacy gene-name importer policy',
        'input_md5': {name: info['md5'] for name, info in status['files'].items()},
    }
    report_path = output.with_name(output.name + '.build.json')

    def save():
        temp = report_path.with_name(report_path.name + '.tmp')
        temp.write_text(json.dumps(report, indent=2) + '\n')
        temp.replace(report_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    # O_EXCL prevents a race with another builder. Incomplete files remain .building.
    if not args.resume_genes:
        with staging.open('xb'):
            pass
    db = sqlite3.connect(staging)
    # Disposable, unpublished build only. Never use these settings on the live DB.
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=FILE; PRAGMA cache_size=-131072; PRAGMA locking_mode=EXCLUSIVE;')
    started = time.monotonic()
    save()
    try:
        resume_rows = 0
        if args.resume_genes:
            if previous['input_md5'] != report['input_md5'] or previous['source_schema'] != str(source):
                raise RuntimeError('Resume input files/reference changed')
            if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise RuntimeError('Staging database failed recovery quick_check')
            actual = db.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC,name").fetchall()
            if actual != [row for row in schema if row[0] == 'table']:
                raise RuntimeError('Recovery requires matching tables and no explicit indexes')
            if db.execute('SELECT count(*) FROM orthodb_to_og').fetchone()[0] != 0:
                raise RuntimeError('Membership loading already started')
            if sorted(db.execute('SELECT * FROM levels').fetchall()) != sorted(levels):
                raise RuntimeError('Staging levels differ from reference')
            resume_rows = db.execute('SELECT count(*) FROM genes').fetchone()[0]
            report['recovered_gene_rows'] = resume_rows
            report['stages']['genes'] = {'rows': resume_rows, 'seconds': 0, 'status': 'rescanning_prefix'}
            print(f'Recovering {resume_rows:,} committed genes; scanning past their gzip prefix without reinserting', flush=True)
            save()
        else:
            for kind, _, sql in schema:
                if kind == 'table':
                    db.execute(sql)
            db.executemany('INSERT INTO levels VALUES (?,?)', levels)
            db.commit()

        def ingest(mode, archive, table):
            count = resume_rows if mode == 'genes' else 0
            initial_count = count
            stage_start = time.monotonic()
            cmd = [str(args.streamer.resolve()), mode, str((args.archives / archive).resolve()), level_arg]
            if count:
                cmd.append(str(count))
            stats_path = output.with_name(output.name + f'.{mode}.json')
            env = dict(os.environ, ORTHODB_STREAM_STATS=str(stats_path))
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env)
            batch = []
            try:
                for line in process.stdout:
                    fields = line.decode('utf-8').rstrip('\n').split('\t')
                    if len(fields) != 3:
                        raise RuntimeError(f'Malformed streamer output for {mode}')
                    if mode == 'genes':
                        row = (int(fields[0]), fields[1] or None, fields[2] or None)
                    else:
                        row = tuple(map(int, fields))
                    batch.append(row)
                    if len(batch) == 50000:
                        db.executemany(f'INSERT INTO {table} VALUES (?,?,?)', batch)
                        db.commit()
                        count += len(batch)
                        batch.clear()
                        if count % 1000000 == 0:
                            elapsed = time.monotonic() - stage_start
                            report['stages'][mode] = {'rows': count, 'seconds': round(elapsed), 'status': 'loading'}
                            save()
                            print(f'{mode}: {count:,} rows, {(count-initial_count) / elapsed:,.0f} new rows/s, database {staging.stat().st_size / 2**30:.2f} GiB', flush=True)
                        if shutil.disk_usage(staging.parent).free < 8 * 2**30:
                            raise RuntimeError('Free disk space below 8 GiB reserve')
                db.executemany(f'INSERT INTO {table} VALUES (?,?,?)', batch)
                db.commit()
                count += len(batch)
                if process.wait() != 0:
                    raise RuntimeError(f'Go streamer failed during {mode}')
            finally:
                process.stdout.close()
                if process.poll() is None:
                    process.terminate()
                    process.wait()
            if not count:
                raise RuntimeError(f'No rows imported for {mode}')
            report['stages'][mode] = {'rows': count, 'seconds': round(time.monotonic() - stage_start), 'status': 'complete'}
            statistics = json.loads(stats_path.read_text())
            if statistics['compatible_records'] != count:
                raise RuntimeError(f'Streamed/imported row count mismatch for {mode}')
            report['stages'][mode].update(statistics)
            save()

        ingest('genes', 'odb13v0_genes.tab.gz', 'genes')
        ingest('memberships', 'odb13v0_OG2genes.tab.gz', 'orthodb_to_og')
        for kind, name, sql in schema:
            if kind == 'index':
                print(f'Building index {name}', flush=True)
                index_start = time.monotonic()
                db.execute(sql)
                db.commit()
                report['stages'][name] = {'seconds': round(time.monotonic() - index_start), 'status': 'complete'}
                save()
        print('Analyzing and validating database', flush=True)
        db.execute('ANALYZE')
        db.commit()
        actual = db.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC,name").fetchall()
        if actual != schema:
            raise RuntimeError('Schema differs from reference')
        check = db.execute('PRAGMA quick_check').fetchall()
        if check != [('ok',)]:
            raise RuntimeError(f'SQLite quick_check failed: {check[:10]}')
        for mode, table in [('genes', 'genes'), ('memberships', 'orthodb_to_og')]:
            actual_count = db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
            if actual_count != report['stages'][mode]['rows']:
                raise RuntimeError(f'Row count mismatch for {table}')
        samples = {}
        for accession in ('Q9UL18', 'Q92484', 'P05026'):
            rows = db.execute('SELECT g.gene_name,m.cluster_id,m.clade FROM genes g JOIN orthodb_to_og m USING(orthodb_id) WHERE g.uniprot_id=? AND m.clade=2759 LIMIT 20', (accession,)).fetchall()
            samples[accession] = rows
        if not samples['Q9UL18']:
            raise RuntimeError('Human AGO1 UniProt lookup returned no Eukaryota membership')
        report['sample_queries'] = samples
        report['quick_check'] = 'ok'
        report['schema_matches_reference'] = True
        db.close()
        ref.close()
        # Publish to the NEW filename only; never replace the active database.
        if output.exists():
            raise RuntimeError('Output appeared during build; refusing replacement')
        with staging.open('rb') as completed:
            os.fsync(completed.fileno())
        os.link(staging, output)  # Atomic creation; cannot replace an existing file.
        staging.unlink()
        report['status'] = 'complete'
        report['seconds'] = round(time.monotonic() - started)
        report['bytes'] = output.stat().st_size
        save()
        print(f'Validated {output}: {report["bytes"] / 2**30:.2f} GiB in {report["seconds"] / 60:.1f} minutes', flush=True)
    except BaseException as exc:
        report['status'] = 'failed'
        report['error'] = str(exc)
        save()
        db.close()
        ref.close()
        raise


if __name__ == '__main__':
    main()
