import asyncio
import urllib.error
from collections import defaultdict
import math
import re
from time import time
import json
from typing import Optional
import itertools

from aioredis.client import Pipeline
import anyio
import pandas as pd

from . import table_sync
from ..task_manager import queue_manager, get_db, ReportErrorException
from ..redis import redis, LEVELS, enqueue, update, happend, report_updates
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


PROTTREE_URL = re.compile(r"(.+)")


async def fetch_proteins(level:str, prots_to_fetch:list[str]):
    db = get_db()
    result: dict[str, list] = {}

    async def progress(items_in_front):
        if items_in_front > 0:
            db.msg = f"In queue to request proteins ({items_in_front} tasks in front)"
        elif items_in_front == 0:
            db.msg = "Getting proteins"


    async def fetch_prot_chunk(chunk:list[str], first_chunk: bool):
        task = table_sync.orthodb_get(level, chunk)
        if first_chunk:
            task.set_progress_callback(progress)
        prots = await task
        prots : defaultdict[str, list]
        db.current += len(prots)
        uniprot_reqs = [
            table_sync.uniprot_get(missing_id)
            for missing_id in set(chunk) - prots.keys()
        ]

        for f in asyncio.as_completed(uniprot_reqs):
            prot_id, data = await f
            if data:
                prots[prot_id].append(data)
                db.current += 1
            else:
                db.total -= 1
                async with redis.pipeline(transaction=True) as pipe:
                    happend(db.state_key, "missing_prots", prot_id, separator=", ", redis_client=pipe)
                    report_updates(db.task_id, "missing_prots", redis_client=pipe)
                    await pipe.execute()

        result.update(prots)

    min_items_per_chunk = 20
    max_items_per_chunk = 200
    preferred_chunk_count = 10

    chunk_count = max(
        min(preferred_chunk_count, math.ceil(len(prots_to_fetch) / min_items_per_chunk)), # target request count
        math.ceil(len(prots_to_fetch) / max_items_per_chunk), # minimal num of requests
    )
    chunk_length = math.ceil(len(prots_to_fetch)/chunk_count)

    async with anyio.create_task_group() as tg:
        for i in range(chunk_count):
            tg.start_soon(
                fetch_prot_chunk,
                prots_to_fetch[i*chunk_length:(i+1)*chunk_length],
                i==0, # first_chunk
            )

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


async def fetch_orthogroups(orthogroups_to_fetch: list[str], dash_columns: list[str]):
    db = get_db()
    async def progress(items_in_front):
        if items_in_front > 0:
            db.msg = f"In queue to request orthogroup info ({items_in_front} tasks in front)"
        elif items_in_front == 0:
            db.msg = "Requesting orthogroup info"
            await db.sync()

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
                    db.current += 1
                    og_info[og] = data
                else:
                    db.total -= 1
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
async def table():
    db = get_db()
    # read request outside of the transaction
    # but we will check the validity very soon after
    prot_req = await db["input_proteins"]

    prot_ids = list(dict.fromkeys( # removing duplicates
        m.group(0)
        for m in VALID_PROT_IDS.finditer(COMMENT.sub("", prot_req).upper())
    ))
    if len(prot_ids) == 0:
        db["table"] = ""
        raise ReportErrorException("Np protrin codes provided!")
    db.current = 0
    db.total = len(prot_ids)
    db.msg = "Getting proteins"
    db["missing_prots"] = None

    level_id = int(await db["input_tax_level"])
    _, level_orthodb_id, _ = LEVELS[level_id]
    res_dict = await table_sync.orthodb_get(level_orthodb_id, prot_ids)

    missing = set(prot_ids).difference(res_dict.keys())
    if missing:
        db["missing_prots"] = ', '.join(missing)

    db.current = 0
    db.total = None
    db.msg = "Getting orthogroup info"

    with atomic_file(db.task_dir / "OG.csv") as tmp_file:
        uniprot_df = await table_sync.process_prot_data(
            list(itertools.chain.from_iterable(
                res_dict.values()
            )),
            tmp_file,
        )
        await db.check_if_cancelled()

    # Can start visualization right now

    @db.transaction
    async def res(pipe: Pipeline):
        pipe.multi()
        await enqueue(
            task_id=db.task_id,
            stage="vis",
            redis_client=pipe,
        )
        update(
            db.task_id, pipe,
            progress_vis_msg='Building visualization',
        )
    await res

    uniprot_df: pd.DataFrame

    og_list = uniprot_df['label']
    db.total = len(og_list)

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

    db.current = len(og_info)
    orthogroups_to_fetch = list(set(og_list)-og_info.keys())

    try:
        if orthogroups_to_fetch:
            og_info.update(
                await fetch_orthogroups(
                    orthogroups_to_fetch=orthogroups_to_fetch,
                    dash_columns=REQUEST_COLUMNS,
                )
            )
    except urllib.error.HTTPError as e:
        if e.code == 502:
            if og_info: # if something is in the cache
                await db.report_error("Some data is missing: orthodb.org sparql server is down", cancel_rest=False)
            else:
                raise ReportErrorException("Data is missing: orthodb.org sparql server is down") from e
        else:
            raise

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

    og_info_df['Name'] = og_info_df['Name'].str.replace(PROTTREE_URL, f"[\\1](/prottree?task_id={db.task_id}&prot_id=\\1)")
    data = og_info_df.to_dict('records'),
    columns = []
    for col_name in og_info_df.columns:
        column = {
            "name": col_name,
            "id": col_name,
        }
        if col_name == "Name":
            column['type'] = 'text'
            column['presentation'] = 'markdown'
        columns.append(column)


    table_data = {
        "data": og_info_df.to_dict('records'),
        "columns": columns
    }

    await table_sync.save_table(db.task_dir / "Info_table.json", table_data)
    db["table"] = db.q_id


