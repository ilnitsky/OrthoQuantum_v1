import asyncio

from aioredis.client import Pipeline
from . import vis_sync

from ..task_manager import get_db, queue_manager, cancellation_manager, ReportErrorException
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
    level, phyloxml_file = LEVELS[level_id]

    organisms, csv_data = await vis_sync.read_org_info(
        phyloxml_file=phyloxml_file,
        og_csv_path=str(db.task_dir/'OG.csv')
    )
    organisms:list[int]
    csv_data: pd.DataFrame

    db.current = 0
    db.total = len(csv_data)

    corr_info_to_fetch = {}
    corr_info = {}
    prot_ids = {}

    cur_time = int(time.time())
    async with redis.pipeline(transaction=False) as pipe:
        for _, data in csv_data.iterrows():
            label=data['label']
            pipe.hgetall(f"/cache/corr/{level}/{label}/data")
            pipe.hgetall(f"/cache/corr/{level}/{label}/gene_names")

            pipe.set(f"/cache/corr/{level}/{label}/accessed", cur_time, xx=True)
        res = iter(await pipe.execute())
        for _, data in csv_data.iterrows():
            og_name=data['Name']
            ortho_counts = next(res)
            gene_names = next(res)
            _ = next(res)
            if ortho_counts:
                corr_info[og_name] = ortho_counts
                prot_ids[og_name] = gene_names
                db.current += 1
            else:
                corr_info_to_fetch[og_name] = data['label']

    if corr_info_to_fetch:
        db.total -= 1
        async def progress(items_in_front):
            if items_in_front > 0:
                db.msg=f"In queue to request correlation data ({items_in_front} tasks in front)"
            elif items_in_front == 0:
                db.msg = "Requesting correlation data"
                db.total = len(corr_info_to_fetch)
                await db.sync()

        corr_info_to_retry = {}
        tasks = [
            vis_sync.get_corr_data(
                name=name,
                label=label,
                level=level,
            )
            for name, label in corr_info_to_fetch.items()
        ]
        tasks[0].set_progress_callback(progress)

        try:
            async with redis.pipeline(transaction=False) as pipe:
                for _ in range(3):
                    for f in asyncio.as_completed(tasks):
                        og_name, ortho_counts, gene_names = await f
                        if ortho_counts is None:
                            corr_info_to_retry[og_name] = corr_info_to_fetch[og_name]
                            continue
                        og_name: str
                        ortho_counts: dict

                        cur_time = int(time.time())
                        label = corr_info_to_fetch[og_name]
                        pipe.hset(f"/cache/corr/{level}/{label}/data", mapping=ortho_counts)
                        pipe.hset(f"/cache/corr/{level}/{label}/gene_names", mapping=gene_names)
                        pipe.set(f"/cache/corr/{level}/{label}/accessed", cur_time)
                        pipe.setnx(f"/cache/corr/{level}/{label}/created", cur_time)

                        corr_info[og_name] = ortho_counts
                        prot_ids[og_name] = gene_names
                        db.current += 1
                    if corr_info_to_retry:
                        corr_info_to_fetch, corr_info_to_retry = corr_info_to_retry, corr_info_to_fetch
                        corr_info_to_retry.clear()
                        await asyncio.sleep(5)
                        tasks = [
                            vis_sync.get_corr_data(
                                name=name,
                                label=label,
                                level=level,
                            )
                            for name, label in corr_info_to_fetch.items()
                        ]
                    else:
                        break
                else:
                    await pipe.execute()
                    raise ReportErrorException(f"Can't fetch correlation info for {';'.join(corr_info_to_fetch.keys())}")
                await pipe.execute()
        except:
            for t in tasks:
                t.cancel()
            raise

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
    db.msg="Processing correlation data"


    # interpret the results:


    df_for_heatmap = df.copy()

    # TODO: db.hide_pb()? set style to ""
    # await db.flush_progress(status="Waiting")

    tasks = []
    tasks.append(
        asyncio.create_task(
            heatmap(
                organism_count=len(organisms),
                df=df_for_heatmap,
            )
        )
    )
    del df_for_heatmap

    tasks.append(
        asyncio.create_task(
            tree(
                phyloxml_file=phyloxml_file,
                OG_names=csv_data['Name'],
                df=df,
                organisms=organisms,
                prot_ids=prot_ids,

                do_blast=blast_enable,
            )
        )
    )

    del csv_data
    del df
    del organisms

    try:
        _, (shape, tree_kind) = await asyncio.gather(*tasks)
    except:
        for task in tasks:
            task.cancel()
        raise


    if blast_enable:
        @db.transaction
        async def res(pipe: Pipeline):
            pipe.multi()
            update(db.task_id, redis_pipe=pipe,
                progress_tree_msg="BLASTing",
                progress_tree_total="",
            )

            await enqueue(
                task_id=db.task_id,
                stage="blast", # for queue selector
                params={
                    "stage": "tree" # for pb report
                },
                redis_client=pipe,

                blast_autoreload="1" if shape[0]*shape[1]<80_000 else "",
                enqueue_tree_gen="1" if tree_kind!="interactive" else "",
            )
        await res

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

