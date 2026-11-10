"""Populate a new demo query from a saved result or a bundled example."""
import shutil

DEMO_EXAMPLES = {
    'uniprot': ('UniProt IDs', 'Q9UL18\nP06748\nQ92484\nP05026'),
    'kegg': ('KEGG', 'ko04210'),
    'interpro': ('InterPro', 'IPR003165'),
}


def populate_demo_task(user, task_id, source_task_id, demo_kind=None):
    if demo_kind is not None and demo_kind not in DEMO_EXAMPLES:
        raise ValueError('Unknown demo type')
    source = user.DATA_PATH / source_task_id
    base = f'/tasks/{source_task_id}'
    target = f'/tasks/{task_id}'
    if demo_kind is None and source.is_dir() and user.db.hget(f'{base}/state', 'tree'):
        shutil.copytree(source, user.DATA_PATH / task_id)
        # Preserve the new query's owner/timestamps and never clone active jobs.
        excluded = {'user_id', 'created', 'accessed', 'enqueued', 'running'}
        with user.db.pipeline(transaction=True) as pipe:
            for key in user.db.scan_iter(match=f'{base}/*'):
                suffix = key[len(base) + 1:]
                if suffix not in excluded:
                    pipe.execute_command('COPY', key, f'{target}/{suffix}', 'REPLACE')
            pipe.execute()
        return 'snapshot'

    # UniProt inputs use the local identifier mapping; BLAST is deliberately off.
    name, proteins = DEMO_EXAMPLES[demo_kind or 'uniprot']
    with user.db.pipeline(transaction=True) as pipe:
        user.update(
            task_id, redis_pipe=pipe,
            title=f'Demo · {name}' if demo_kind else 'Demo query', input_proteins=proteins,
            input_proteins_parsed=proteins, input_tax_level='1', taxid_input='9606',
            input_blast_enabled='', input_blast_evalue='', input_blast_pident='',
            input_blast_qcovs='', input_max_proteins='600', extra_auto_select='1',
            extra_table_selected_rows='[]', missing_prots='',
            progress_table_style='progress', progress_table_msg='Loading demo',
            progress_table_max=str(len(proteins.splitlines())), progress_table_value='0',
        )
        user.enqueue(task_id, 'table', redis_client=pipe)
        pipe.execute()
    return 'example'
