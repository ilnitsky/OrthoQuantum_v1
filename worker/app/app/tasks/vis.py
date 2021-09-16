import asyncio

from aioredis.client import Pipeline
from . import vis_sync

from ..task_manager import get_db, queue_manager, cancellation_manager
from ..redis import redis, LEVELS, enqueue

from .tree_heatmap import tree, heatmap

import time
import pandas as pd
import numpy as np


@queue_manager.add_handler("/queues/vis")
@cancellation_manager.wrap_handler
async def vis():
    db = get_db()
    @db.transaction
    async def res(pipe: Pipeline):
        pipe.multi()
        db.report_progress(
            current=0,
            total=-1,
            message="Getting correlation data",
            status="Executing",
            pipe=pipe,
        )
        pipe.hset(f"/tasks/{db.task_id}/progress/tree", "status", "Waiting")
        pipe.hset(f"/tasks/{db.task_id}/progress/heatmap", "status", "Waiting")

        pipe.mget(
            f"/tasks/{db.task_id}/request/blast_enable",
            f"/tasks/{db.task_id}/request/tax-level"
        )

    blast_enable, level_id = (await res)[-1]
    blast_enable = bool(blast_enable)
    level_id = int(level_id)
    level, phyloxml_file = LEVELS[level_id]

    organisms, csv_data = await vis_sync.read_org_info(
        phyloxml_file=phyloxml_file,
        og_csv_path=str(db.task_dir/'OG.csv')
    )
    organisms:list[int]
    csv_data: pd.DataFrame

    db.report_progress(
        current=0,
        total=len(csv_data),
    )

    corr_info_to_fetch = {}
    corr_info = {}

    cur_time = int(time.time())
    async with redis.pipeline(transaction=False) as pipe:
        for _, data in csv_data.iterrows():
            label=data['label']
            pipe.hgetall(f"/cache/corr/{level}/{label}/data")
            pipe.set(f"/cache/corr/{level}/{label}/accessed", cur_time, xx=True)
        res = (await pipe.execute())[::2]
        for (_, data), cache in zip(csv_data.iterrows(), res):
            og_name=data['Name']
            if cache:
                corr_info[og_name] = cache
                db.report_progress(current_delta=1)
            else:
                corr_info_to_fetch[og_name] = data['label']

    if corr_info_to_fetch:
        db.report_progress(total=-1)
        async def progress(items_in_front):
            if items_in_front > 0:
                db.report_progress(
                    message=f"In queue to request correlation data ({items_in_front} tasks in front)",
                )
            elif items_in_front == 0:
                await db.flush_progress(
                    message="Requesting correlation data",
                    total=len(corr_info_to_fetch)
                )

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
                for f in asyncio.as_completed(tasks):
                    og_name, data = await f
                    og_name: str
                    data: dict

                    cur_time = int(time.time())
                    label = corr_info_to_fetch[og_name]
                    pipe.hset(f"/cache/corr/{level}/{label}/data", mapping=data)
                    pipe.set(f"/cache/corr/{level}/{label}/accessed", cur_time)
                    pipe.setnx(f"/cache/corr/{level}/{label}/created", cur_time)

                    corr_info[og_name] = data
                    db.report_progress(current_delta=1)

                await pipe.execute()
        except:
            for t in tasks:
                t.cancel()
            raise

    df = pd.DataFrame(
        data={
            col_name: pd.Series(
                data=data.values(),
                index=np.fromiter(data.keys(), count=len(data), dtype=np.int64),
                name=col_name,
            )
            for col_name, data in corr_info.items()
        },
        index=organisms,
    )
    df.fillna(0, inplace=True)
    df = df.astype(np.int8, copy=False)
    db.report_progress(message="Processing correlation data")


    # interpret the results:


    df_for_heatmap = df.copy()

    await db.flush_progress(status="Waiting")
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
            await enqueue(
                version_key=f"/tasks/{db.task_id}/stage/blast/version",
                queue_key="/queues/blast",
                queue_id_dest=f"/tasks/{db.task_id}/progress/blast",
                queue_hash_key="q_id",
                redis_client=pipe,

                task_id=db.task_id,
                stage="blast",
                blast_autoreload="1" if shape[0]*shape[1]<80_000 else "",
                enqueue_tree_gen="1" if tree_kind!="interactive" else "",
            )
            pipe.hset(f"/tasks/{db.task_id}/progress/blast",
                mapping={
                    "status": 'Enqueued',
                    'total': -1,
                    "message": "BLASTing",
                }
            )

        await res

    await db.flush_progress(status="Done", version=db.version)