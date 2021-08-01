import asyncio
from collections import defaultdict
import math
import re
from time import time
import json
from typing import Optional
import itertools

from aioredis.client import Pipeline
import pandas as pd

from . import table_sync
from ..task_manager import DbClient, queue_manager, cancellation_manager
from ..redis import redis, LEVELS, enqueue
from ..utils import atomic_file


TABLE_COLUMNS = [
    "label",
    "Name",
    "description",
    "clade",
    "evolRate",
    "totalGenesCount",
    "multiCopyGenesCount",
    "singleCopyGenesCount",
    "inSpeciesCount",
    # "medianExonsCount", "stddevExonsCount",
    "medianProteinLength",
    "stddevProteinLength"
]

REQUEST_COLUMNS = TABLE_COLUMNS.copy()
try:
    REQUEST_COLUMNS.remove("Name")
except ValueError:
    pass
REQUEST_COLUMNS.append("og")



async def fetch_proteins(db: DbClient, level:str, prots_to_fetch:list[str]):
    result: dict[str, list] = {}

    async def progress(items_in_front):
        if items_in_front > 0:
            db.report_progress(
                message=f"In queue to request proteins ({items_in_front} tasks in front)",
            )
        elif items_in_front == 0:
            await db.flush_progress(
                message="Getting proteins",
            )

    async def fetch_prot_chunk(chunk:list[str], first_chunk: bool):
        task = table_sync.orthodb_get(level, chunk)
        if first_chunk:
            task.set_progress_callback(progress)
        prots = await task
        prots : defaultdict[str, list]
        db.report_progress(current_delta=len(prots))
        uniprot_reqs = [
            table_sync.uniprot_get(missing_id)
            for missing_id in set(chunk) - prots.keys()
        ]

        for f in asyncio.as_completed(uniprot_reqs):
            prot_id, data = await f
            if data:
                prots[prot_id].append(data)
                db.report_progress(current_delta=1)
            else:
                db.report_progress(total_delta=-1)
                await redis.append(f"/tasks/{db.task_id}/stage/{db.stage}/missing_msg", f"{prot_id}, ")

        result.update(prots)

    min_items_per_chunk = 20
    max_items_per_chunk = 200
    preferred_chunk_count = 10

    chunk_count = max(
        min(preferred_chunk_count, math.ceil(len(prots_to_fetch) / min_items_per_chunk)), # target request count
        math.ceil(len(prots_to_fetch) / max_items_per_chunk), # minimal num of requests
    )
    chunk_length = math.ceil(len(prots_to_fetch)/chunk_count)
    tasks = [
        asyncio.create_task(fetch_prot_chunk(
            # chunk
            prots_to_fetch[i*chunk_length:(i+1)*chunk_length],
            first_chunk=i==0,
        ))
        for i in range(chunk_count)
    ]

    try:
        await asyncio.gather(*tasks)
    except:
        for t in tasks:
            t.cancel()
        raise

    cur_time = int(time())
    async with redis.pipeline(transaction=False) as pipe:
        # Add all prots to the cache
        for prot_id, prot_data in result.items():
            pipe.mset(
                {
                    f"/cache/uniprot/{level}/{prot_id}/data": json.dumps(prot_data, separators=(',', ':')),
                    f"/cache/uniprot/{level}/{prot_id}/accessed": cur_time,
                }
            )
            pipe.setnx(f"/cache/uniprot/{level}/{prot_id}/created", cur_time)
        await pipe.execute()
    return result


async def fetch_orthogroups(db: DbClient, orthogroups_to_fetch: list[str], dash_columns: list[str]):
    async def progress(items_in_front):
        if items_in_front > 0:
            db.report_progress(
                message=f"In queue to request orthogroup info ({items_in_front} tasks in front)",
            )
        elif items_in_front == 0:
            await db.flush_progress(
                message="Requesting orthogroup info",
            )

    min_items_per_chunk = 10
    max_items_per_chunk = 50
    preferred_chunk_count = 10

    chunk_count = max(
        min(preferred_chunk_count, math.ceil(len(orthogroups_to_fetch) / min_items_per_chunk)), # target request count
        math.ceil(len(orthogroups_to_fetch) / max_items_per_chunk), # minimal num of requests
    )
    chunk_length = math.ceil(len(orthogroups_to_fetch)/chunk_count)

    tasks = [
        table_sync.ortho_data_get(
            orthogroups_to_fetch[i*chunk_length:(i+1)*chunk_length],
            dash_columns,
        )
        for i in range(chunk_count)
    ]
    tasks[0].set_progress_callback(progress)

    og_info : dict[str, dict[str, str]] = {}


    try:
        for f in asyncio.as_completed(tasks):
            og_info_part = await f
            og_info_part: dict[str, Optional[dict[str, str]]]

            for og, data in og_info_part.items():
                if data:
                    db.report_progress(current_delta=1)
                    og_info[og] = data
                else:
                    db.report_progress(total_delta=-1)
    except:
        for t in tasks:
            t.cancel()
        raise

    cur_time = int(time())
    async with redis.pipeline(transaction=False) as pipe:
        for og, og_data in og_info.items():
            pipe.hset(f"/cache/ortho/{og}/data", mapping=og_data)
            pipe.set(f"/cache/ortho/{og}/accessed", cur_time)
            pipe.setnx(f"/cache/ortho/{og}/created", cur_time)
        await pipe.execute()

    return og_info

# https://www.uniprot.org/help/accession_numbers
VALID_PROT_IDS = re.compile(r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}")
COMMENT = re.compile(r"#.*\n")


@queue_manager.add_handler("/queues/table")
@cancellation_manager.wrap_handler
async def table(db: DbClient):
    prot_req = await redis.get(f"/tasks/{db.task_id}/request/proteins")

    prot_ids = list(dict.fromkeys( # removing duplicates
        m.group(0)
        for m in VALID_PROT_IDS.finditer(COMMENT.sub("", prot_req).upper())
    ))
    @db.transaction
    async def res(pipe:Pipeline):
        pipe.multi()
        db.report_progress(
            current=0,
            total=len(prot_ids),
            message="Getting proteins",
            status="Executing",
            pipe=pipe,
        )
        pipe.get(f"/tasks/{db.task_id}/request/tax-level")

    level_id = int((await res)[-1])
    level, _ = LEVELS[level_id]

    # Filter out already cached proteins
    cache_data = await redis.mget([
        f"/cache/uniprot/{level}/{prot_id}/data"
        for prot_id in prot_ids
    ])

    res_dict = {}

    cur_time = int(time())
    async with redis.pipeline(transaction=False) as pipe:
        for prot_id, cache in zip(prot_ids, cache_data):
            if cache is None:
                continue
            pipe.set(f"/cache/uniprot/{level}/{prot_id}/accessed", cur_time, xx=True)
            res_dict[prot_id] = json.loads(cache)
        await pipe.execute()

    await db.flush_progress(current=len(res_dict))
    prots_to_fetch = list(
        set(prot_ids) - res_dict.keys()
    )

    if prots_to_fetch:
        res_dict.update(
            await fetch_proteins(
                db=db,
                level=level,
                prots_to_fetch=prots_to_fetch,
            )
        )

    db.report_progress(current=0, total=-1, message="Getting orthogroup info")

    with atomic_file(db.task_dir / "OG.csv") as tmp_file:
        uniprot_df = await table_sync.process_prot_data(
            list(itertools.chain.from_iterable(
                res_dict.values()
            )),
            tmp_file,
        )

    # Can start visualization right now
    @db.transaction
    async def res(pipe: Pipeline):
        pipe.multi()
        await enqueue(
            version_key=f"/tasks/{db.task_id}/stage/vis/version",
            queue_key="/queues/vis",
            queue_id_dest=f"/tasks/{db.task_id}/progress/vis",
            queue_hash_key="q_id",
            redis_client=pipe,

            task_id=db.task_id,
            stage="vis",
        )
        pipe.hset(f"/tasks/{db.task_id}/progress/vis",
            mapping={
                "status": 'Enqueued',
                'total': -1,
                "message": "Building visualization",
            }
        )
    await res

    uniprot_df: pd.DataFrame

    og_list = uniprot_df['label']
    db.report_progress(total=len(og_list))

    orthogroups_to_fetch = []

    og_info = defaultdict(dict)

    cur_time = int(time())
    async with redis.pipeline(transaction=False) as pipe:
        for og in og_list:
            pipe.hmget(f"/cache/ortho/{og}/data", REQUEST_COLUMNS)
            pipe.set(f"/cache/ortho/{og}/accessed", cur_time, xx=True)

        cache_data = (await pipe.execute())[::2]

    for og, data in zip(og_list, cache_data):
        if None in data:
            continue
        og_info[og] = dict(zip(REQUEST_COLUMNS, data))

    db.report_progress(current_delta=len(og_info))
    orthogroups_to_fetch = list(set(og_list)-og_info.keys())

    if orthogroups_to_fetch:
        og_info.update(
            await fetch_orthogroups(
                db=db,
                orthogroups_to_fetch=orthogroups_to_fetch,
                dash_columns=REQUEST_COLUMNS,
            )
        )


    og_info_df = pd.DataFrame(
        (
            vals.values()
            for vals in og_info.values()
        ),
        columns=REQUEST_COLUMNS,
    )
    og_info_df = pd.merge(og_info_df, uniprot_df, on='label')

    og_info_df = og_info_df[TABLE_COLUMNS]
    #prepare datatable update
    table_data = {
        "version": db.version,
        "data": {
            "data": og_info_df.to_dict('records'),
            "columns": [
                {
                    "name": i,
                    "id": i,
                }
                for i in og_info_df.columns
            ]
        }
    }
    await table_sync.save_table(db.task_dir / "Info_table.json", table_data)


    db.report_progress(
        status="Done",
        version=db.version,
    )
