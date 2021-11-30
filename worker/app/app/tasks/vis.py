from . import vis_sync
import anyio
from ..task_manager import get_db, queue_manager, ReportErrorException
from ..redis import redis, LEVELS, enqueue, update
from ..utils import atomic_file, decode_int
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

    if len(csv_data) == 0: # < 2?
        raise ReportErrorException("Not enough proteins to build correlation")

    db.current = 0
    db.total = len(csv_data)

    corr_info_to_fetch = {}
    corr_info = {}
    prot_ids = {}

    for _, data in csv_data.iterrows():
        name =data['Name']
        label = data['label']
        og_name, ortho_counts, gene_names = await vis_sync.get_corr_data(
            name=name,
            label=label,
            level=level,
        )
        db.current += 1
        corr_info[og_name] = ortho_counts
        prot_ids[og_name] = gene_names



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
    df.fillna(0, inplace=True)
    df = df.astype(np.int16, copy=False)


    # interpret the results:


    df_for_heatmap = df.copy()
    del db.msg
    db.pb_hide()

    async with anyio.create_task_group() as tg:
        tg.start_soon(
            heatmap,
            len(organisms),
            df_for_heatmap,
        )
        del df_for_heatmap
        tg.start_soon(
            tree,
            blast_enable,
            phyloxml_file,
            csv_data['Name'], # OG_names
            df,
            organisms,
            prot_ids,
        )
        del csv_data
        del df
        del organisms


@queue_manager.add_handler("/queues/tree_csv")
async def build_tree_csv():
    async with get_db().substage("tree_csv") as db:
        db.msg = "Generating CSV"

        try:
            with atomic_file(db.task_dir/'tree.csv') as tmp_path:
                await vis_sync.csv_generator(
                    str((db.task_dir/'tree.xml').absolute()),
                    tmp_path,
                )
        except:
            db.report_error("Error while building the csv", cancel_rest=False)
            raise

