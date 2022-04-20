from . import vis_sync
import anyio
from ..task_manager import get_db, queue_manager, ReportErrorException
from ..redis import LEVELS
from ..utils import decode_int
from .tree_heatmap import tree, heatmap

import pandas as pd
import numpy as np


@queue_manager.add_handler("/queues/vis")
async def vis():
    db = get_db()
    db.msg = "Getting correlation data"
    db.total = None

    blast_enable, level_id, max_prots = await db[
        "input_blast_enabled",
        "input_tax_level",
        "input_max_proteins",
    ]

    blast_enable = bool(blast_enable)
    level_id, max_prots = decode_int(level_id, max_prots)
    level, _, phyloxml_file = LEVELS[level_id]

    organisms, csv_data = await vis_sync.read_org_info(
        phyloxml_file=phyloxml_file,
        og_csv_path=str(db.task_dir/'OG.csv')
    )
    organisms:list[int]
    csv_data: pd.DataFrame
    no_uniprot_idx = csv_data[csv_data['UniProt_AC']==''].index
    if not no_uniprot_idx.empty:
        db['missing_uniprot'] = csv_data.loc[no_uniprot_idx, "label"].str.cat(sep=", ")
        csv_data.drop(no_uniprot_idx, inplace=True)
    else:
        db['missing_uniprot'] = ''

    if len(csv_data) == 0:
        await db.report_error("Not enough proteins to build correlation", cancel_rest=False)
        return

    corr_info, prot_ids = await vis_sync.get_corr_data(csv_data)

    db.msg="Processing correlation data"

    df = pd.DataFrame(
        data={
            col_name: pd.Series(
                data=ortho_counts.values(),
                index=np.fromiter(ortho_counts.keys(), count=len(ortho_counts), dtype=np.int64),
                name=col_name,
            )
            for col_name, ortho_counts in corr_info.items()
        },
        index=organisms,
    )
    del organisms

    df.fillna(0, inplace=True)
    df = df.astype(np.int16, copy=False)

    # interpret the results:
    del db.msg
    db.pb_hide()

    if df.shape[1] <= max_prots:
        # can run in parallel

        async with anyio.create_task_group() as tg:
            tg.start_soon(
                heatmap,
                df.shape[0],
                df.copy(),
            )
            tg.start_soon(
                tree,
                blast_enable,
                phyloxml_file,
                csv_data[['label', 'Name']], # OG_names
                df,
                prot_ids,
            )
            del csv_data
            del df
    else:
        prots_to_exclude = await heatmap(df.shape[0], df.copy(), max_prots=max_prots)

        await tree(
            blast_enable,
            phyloxml_file,
            csv_data['Name'][~csv_data['Name'].isin(prots_to_exclude)], # OG_names
            df,
            prot_ids
        )


@queue_manager.add_handler("/queues/tree_csv")
async def build_tree_csv(tgt_connection_id, csv_render_n):
    db = get_db()
    db.msg = "Generating CSV"
    db.total = None

    tree_ver, tree_blast_ver = await db["tree_version", "tree_blast_ver"]

    async with db.atomic_file(db.task_dir/'tree.csv') as tmp_path:
        await vis_sync.csv_generator(
            str((db.task_dir/'tree.xml').absolute()),
            tmp_path,
        )
    tree_blast_ver = tree_blast_ver or 0

    db['tree_csv_ver'] = f'{tree_ver}_{tree_blast_ver}'
    db['tree_csv_download_on_connection_id'] = tgt_connection_id
    db['csv_render_n'] = csv_render_n

