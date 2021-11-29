import asyncio

from aioredis.client import Pipeline
from . import vis_sync
import anyio
from ..task_manager import get_db, queue_manager, ReportErrorException
from ..redis import redis, LEVELS, enqueue, update
from ..utils import atomic_file, decode_int
from .tree_heatmap import tree, heatmap

import time
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



    # cur_time = int(time.time())
    # async with redis.pipeline(transaction=False) as pipe:
    #     for _, data in csv_data.iterrows():
    #         label=data['label']
    #         pipe.hgetall(f"/cache/corr/{level}/{label}/data")
    #         pipe.hgetall(f"/cache/corr/{level}/{label}/gene_names")

    #         pipe.set(f"/cache/corr/{level}/{label}/accessed", cur_time, xx=True)
    #     res = iter(await pipe.execute())
    #     for _, data in csv_data.iterrows():
    #         og_name=data['Name']
    #         ortho_counts = next(res)
    #         gene_names = next(res)
    #         _ = next(res)
    #         if ortho_counts:
    #             corr_info[og_name] = ortho_counts
    #             prot_ids[og_name] = gene_names
    #             db.current += 1
    #         else:
    #             corr_info_to_fetch[og_name] = data['label']

    # if corr_info_to_fetch:
    #     db.total -= 1
    #     async def progress(items_in_front):
    #         if items_in_front > 0:
    #             db.msg=f"In queue to request correlation data ({items_in_front} tasks in front)"
    #         elif items_in_front == 0:
    #             db.msg = "Requesting correlation data"
    #             db.total = len(corr_info_to_fetch)
    #             await db.sync()

    #     # corr_info_to_retry = {}
    #     # tasks = [
    #     #     vis_sync.get_corr_data(
    #     #         name=name,
    #     #         label=label,
    #     #         level=level,
    #     #     )
    #     #     for name, label in corr_info_to_fetch.items()
    #     # ]
    #     # tasks[0].set_progress_callback(progress)




    #     try:
    #         async with redis.pipeline(transaction=False) as pipe:
    #             for _ in range(3):
    #                 for f in asyncio.as_completed(tasks):
    #                         # if ortho_counts is None:
    #                         #     corr_info_to_retry[og_name] = corr_info_to_fetch[og_name]
    #                         #     continue

    #                         # cur_time = int(time.time())
    #                         # pipe.hset(f"/cache/corr/{level}/{label}/data", mapping=ortho_counts)
    #                     # pipe.hset(f"/cache/corr/{level}/{label}/gene_names", mapping=gene_names)
    #                     # pipe.set(f"/cache/corr/{level}/{label}/accessed", cur_time)
    #                     # pipe.setnx(f"/cache/corr/{level}/{label}/created", cur_time)


    #                     db.current += 1
    #                 # if corr_info_to_retry:
    #                 #     corr_info_to_fetch, corr_info_to_retry = corr_info_to_retry, corr_info_to_fetch
    #                 #     corr_info_to_retry.clear()
    #                 #     await asyncio.sleep(5)
    #                 #     tasks = [
    #                 #         vis_sync.get_corr_data(
    #                 #             name=name,
    #                 #             label=label,
    #                 #             level=level,
    #                 #         )
    #                 #         for name, label in corr_info_to_fetch.items()
    #                 #     ]
    #                 else:
    #                     break
    #             else:
    #                 await pipe.execute()
    #                 raise ReportErrorException(f"Can't fetch correlation info for {';'.join(corr_info_to_fetch.keys())}")
    #             await pipe.execute()
    #     except:
    #         for t in tasks:
    #             t.cancel()
    #         raise
    # db.msg="Processing correlation data"

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

