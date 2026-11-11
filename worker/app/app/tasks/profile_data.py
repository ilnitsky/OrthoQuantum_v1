"""Load selected-species profiles without random per-membership gene joins."""
from collections import defaultdict
import hashlib
import json
import logging
import time


def read_cached_profiles(connection, rows, organisms, translation, cache, source_identity):
    """Cache by release file, taxa, aliases and group, independent of UI labels."""
    signature = hashlib.sha256(json.dumps(
        [source_identity, sorted(map(int, organisms)), sorted(translation.items())],
        separators=(',', ':')).encode()).hexdigest()
    keys = [f'/cache/profiles/v2/{signature}/{row["label"]}' for row in rows]
    try:
        cached = cache.mget(keys) if keys else []
    except Exception:
        logging.exception('Profile cache read failed; using reference database')
        cached = [None] * len(rows)
    counts, proteins, missing = {}, {}, []
    for row, value in zip(rows, cached):
        if value:
            try:
                profile, names = json.loads(value)
                counts[row['Name']] = {int(t): v for t, v in profile.items()}
                proteins[row['Name']] = {int(t): v for t, v in names.items()}
                continue
            except (ValueError, TypeError, AttributeError):
                pass
        missing.append(row)
    started = time.monotonic()
    if missing:
        fresh_counts, fresh_names = read_profiles(connection, missing, organisms, translation)
        counts.update(fresh_counts)
        proteins.update(fresh_names)
        try:
            with cache.pipeline(transaction=False) as pipe:
                for row in missing:
                    key = f'/cache/profiles/v2/{signature}/{row["label"]}'
                    pipe.setex(key, 7 * 86400, json.dumps([
                        fresh_counts[row['Name']], fresh_names[row['Name']]]))
                pipe.execute()
        except Exception:
            logging.exception('Profile cache write failed')
    print(f'Species profiles: {len(rows)-len(missing)} cached, {len(missing)} loaded in {time.monotonic()-started:.2f}s', flush=True)
    return counts, proteins


def read_profiles(connection, rows, organisms, translation):
    selected = set(map(int, organisms))
    selected.update(old for old, current in translation.items() if current in selected)
    memberships = []
    requested_genes = set()
    for row in rows:
        cluster, clade = map(int, row['label'].split('at'))
        # Memberships are much smaller than the gene/xref join. Deduplicate here
        # before looking up names, and filter taxa before touching the genes table.
        genes = {gene for (gene,) in connection.execute(
            'SELECT orthodb_id FROM orthodb_to_og WHERE clade=? AND cluster_id=?',
            (clade, cluster)) if gene >> 32 in selected}
        memberships.append((row['Name'], genes))
        requested_genes.update(genes)

    gene_names = defaultdict(set)
    ordered = sorted(requested_genes)
    # The gene table is laid out in organism/gene order. Sorted lookups reduce
    # disk seeks and resolve shared genes once per batch rather than once per OG.
    for start in range(0, len(ordered), 500):
        batch = ordered[start:start + 500]
        marks = ','.join('?' for _ in batch)
        for gene, name in connection.execute(
                f'SELECT orthodb_id,gene_name FROM genes WHERE orthodb_id IN ({marks}) ORDER BY orthodb_id', batch):
            if name is not None:
                gene_names[gene].add(name)

    correlations, proteins = {}, {}
    for name, genes in memberships:
        counts = defaultdict(int)
        names = defaultdict(set)
        for gene in sorted(genes):
            taxid = translation.get(gene >> 32, gene >> 32)
            counts[taxid] += 1
            names[taxid].update(gene_names[gene])
        correlations[name] = dict(counts)
        proteins[name] = {taxid: ', '.join(sorted(names[taxid])) or 'None' for taxid in counts}
    return correlations, proteins
