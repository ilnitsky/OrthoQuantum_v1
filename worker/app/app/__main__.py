import asyncio
from collections import defaultdict
import json
import math
import traceback
from typing import Optional
from pathlib import Path

from aioredis.client import Pipeline
from . import async_tasks


import aioredis

from .async_executor import async_pool
from .redis import redis, QUEUE, GROUP, CONSUMER
from .task_manager import CancellationManager, DbClient
from .utils import decode_int, DEBUG, atomic_file


import re
import time
import itertools
import pandas as pd

MAX_RUNNING_JOBS = 10

LEVELS = {}

async def init_availible_levels():
    global LEVELS
    phyloxml_dir = Path.cwd() / "phyloxml"
    l = []
    for file in phyloxml_dir.glob("*.xml"):
        items = file.stem.split("_", maxsplit=2)
        if len(items) == 3:
            id, level, name = items
        elif len(items) == 2:
            id, level = items
            name = level
        else:
            raise RuntimeError(f"incorrect file name {file}")

        l.append(
            (
                int(id),
                level,
                name,
                str(file.resolve()),
            )
        )
    l.sort()

    availible_levels = {}
    for id, level, name, path in l:
        LEVELS[id] = (level, path)
        availible_levels[name] = id

    await redis.set("/availible_levels", json.dumps(availible_levels))

async def queue_manager():
    """Grabs work from the db and schedules it"""
    try:
        res = await redis.xgroup_create(QUEUE, GROUP, id="0", mkstream=True)
    except aioredis.ResponseError as e:
        # ignoring an error if the consumer group already exists
        if not e.args[0].startswith('BUSYGROUP'):
            raise

    cur_running = set()

    async with redis as r, CancellationManager() as cm:
        last_id = "0"
        while True:
            while len(cur_running) >= MAX_RUNNING_JOBS:
                _, cur_running = await asyncio.wait(cur_running, return_when=asyncio.FIRST_COMPLETED)

            res = await r.xreadgroup(
                GROUP, CONSUMER, {QUEUE: last_id},
                count=MAX_RUNNING_JOBS-len(cur_running), block=60000,
            )
            if not res:
                # Timeout, continue polling
                continue
            assert len(res) == 1, "Response contains multiple queues"

            queue_name, items = res[0]
            assert queue_name == QUEUE, "Response contains unknown queue"

            if last_id != ">":
                if not items:
                    # processed all of the unACKnowledged messages, go to longpoll
                    last_id = ">"
                    continue
                else:
                    # next time sending the last item's ID
                    last_id = items[-1][0]

            for q_id, data in items:
                print("Enqueueing", q_id, data)
                if data["stage"] == "flush_cache":
                    cur_running.add(
                        asyncio.create_task(
                            flush_cache(q_id)
                        )
                    )
                    continue

                db = DbClient(
                    q_id=q_id,
                    task_id=data["task_id"],
                    stage=data["stage"],
                    version=decode_int(data["version"]),
                )
                if data["stage"] == "table":
                    cur_running.add(cm.run_task(
                        table,
                        db=db,
                    ))
                elif data["stage"] == "sparql":
                    cur_running.add(cm.run_task(
                        sparql,
                        db=db,
                    ))


async def flush_cache(q_id):
    async with redis.pipeline(transaction=False) as pipe:
        async for items in redis.scan_iter(match="/cache/*"):
            pipe.delete(items)
        pipe.xack(QUEUE, GROUP, q_id)
        await pipe.execute()
    print("Cache flushed")


INVALID_PROT_IDS = re.compile(r"[^A-Za-z0-9\-\n \t]+")

async def delay():
    await asyncio.sleep(0)

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
        task = async_tasks.orthodb_get(level, chunk)
        if first_chunk:
            task.set_progress_callback(progress)
        prots = await task
        prots : defaultdict[str, list]
        db.report_progress(current_delta=len(prots))
        uniprot_reqs = [
            async_tasks.uniprot_get(missing_id)
            for missing_id in set(chunk) - prots.keys()
        ]

        for f in asyncio.as_completed(uniprot_reqs):
            prot_id, data = await f
            await delay()
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

    cur_time = int(time.time())
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
        async_tasks.ortho_data_get(
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

    cur_time = int(time.time())
    async with redis.pipeline(transaction=False) as pipe:
        for og, og_data in og_info.items():
            pipe.hset(f"/cache/ortho/{og}/data", mapping=og_data)
            pipe.set(f"/cache/ortho/{og}/accessed", cur_time)
            pipe.setnx(f"/cache/ortho/{og}/created", cur_time)
        await pipe.execute()

    return og_info



async def table(db: DbClient):
    prot_req = await redis.get(f"/tasks/{db.task_id}/request/proteins")
    prot_ids = list(dict.fromkeys( # removing duplicates
        INVALID_PROT_IDS.sub("", prot_req).upper().split(),
    ))
    @db.transaction
    async def res(pipe:Pipeline):
        pipe.multi()
        db.report_progress(
            current=0,
            total=len(prot_ids),
            message="Getting proteins",
            pipe=pipe,
        )
        pipe.set(f"/tasks/{db.task_id}/stage/{db.stage}/status", "Executing")
        pipe.get(f"/tasks/{db.task_id}/request/dropdown1")

    level_id = int((await res)[-1])
    level, _ = LEVELS[level_id]

    # Filter out already cached proteins
    cache_data = await redis.mget([
        f"/cache/uniprot/{level}/{prot_id}/data"
        for prot_id in prot_ids
    ])

    res_dict = {}

    cur_time = int(time.time())
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
        uniprot_df = await async_tasks.process_prot_data(
            list(itertools.chain.from_iterable(
                res_dict.values()
            )),
            tmp_file,
        )
    uniprot_df: pd.DataFrame

    og_list = uniprot_df['label']
    db.report_progress(total=len(og_list))

    dash_columns = [
        "label",
        "description",
        "clade",
        "evolRate",
        "totalGenesCount",
        "multiCopyGenesCount",
        "singleCopyGenesCount",
        "inSpeciesCount",
        # "medianExonsCount", "stddevExonsCount",
        "medianProteinLength",
        "stddevProteinLength",
        "og"
    ]

    orthogroups_to_fetch = []

    og_info = defaultdict(dict)

    cur_time = int(time.time())
    async with redis.pipeline(transaction=False) as pipe:
        for og in og_list:
            pipe.hmget(f"/cache/ortho/{og}/data", dash_columns)
            pipe.set(f"/cache/ortho/{og}/accessed", cur_time, xx=True)

        cache_data = (await pipe.execute())[::2]

    for og, data in zip(og_list, cache_data):
        if None in data:
            continue
        og_info[og] = dict(zip(dash_columns, data))

    db.report_progress(current_delta=len(og_info))
    orthogroups_to_fetch = list(set(og_list)-og_info.keys())

    if orthogroups_to_fetch:
        og_info.update(
            await fetch_orthogroups(
                db=db,
                orthogroups_to_fetch=orthogroups_to_fetch,
                dash_columns=dash_columns,
            )
        )


    og_info_df = pd.DataFrame(
        (
            vals.values()
            for vals in og_info.values()
        ),
        columns=dash_columns,
    )
    og_info_df = pd.merge(og_info_df, uniprot_df, on='label')

    display_columns = [
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
    og_info_df = og_info_df[display_columns]

    #prepare datatable update
    table_data = {
        "data": og_info_df.to_dict('records'),
        "columns": [
            {
                "name": i,
                "id": i,
            }
            for i in og_info_df.columns
        ]
    }
    table = json.dumps(table_data, ensure_ascii=False, separators=(',', ':'))

    @db.transaction
    async def tx(pipe: Pipeline):
        pipe.multi()
        pipe.mset({
            f"/tasks/{db.task_id}/stage/{db.stage}/status": "Done",
            f"/tasks/{db.task_id}/stage/{db.stage}/dash-table": table,
        })
    await tx

async def main():
    for i in range(10):
        try:
            await redis.ping()
            break
        except Exception:
            await asyncio.sleep(1)
    await init_availible_levels()
    async with async_pool:
        await queue_manager()


async def sparql(db: DbClient):
    @db.transaction
    async def res(pipe: Pipeline):
        pipe.multi()
        pipe.set(f"/tasks/{db.task_id}/stage/{db.stage}/status", "Executing")
        pipe.set(f"/tasks/{db.task_id}/stage/{db.stage}/heatmap-message", "waiting")

        db.report_progress(
            current=0,
            total=-1,
            message="getting correlation data",
            pipe=pipe,
        )
        pipe.get(f"/tasks/{db.task_id}/request/dropdown2")

    level_id = int((await res)[-1])
    level, phyloxml_file = LEVELS[level_id]

    organisms, csv_data = await async_tasks.read_org_info(
        phyloxml_file=phyloxml_file,
        og_csv_path=str(db.task_dir/'OG.csv')
    )
    organisms:list[str]
    csv_data: pd.DataFrame

    db.report_progress(
        current=0,
        total=len(csv_data),
    )

    df = pd.DataFrame(data={"Organisms": organisms}, dtype=object)
    df.set_index('Organisms', inplace=True)
    corr_info_to_fetch = {}

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
                df[og_name] = pd.Series(
                    map(int, cache.values()),
                    index=cache.keys(),
                    name=og_name,
                    dtype=int,
                )
                db.report_progress(current_delta=1)
            else:
                corr_info_to_fetch[og_name] = data['label']

        # res["org_name"]["value"]: int(res["count_orthologs"]["value"]

    if corr_info_to_fetch:
        async def progress(items_in_front):
            if items_in_front > 0:
                db.report_progress(
                    message=f"In queue to request correlation data ({items_in_front} tasks in front)",
                )
            elif items_in_front == 0:
                await db.flush_progress(
                    message="Requesting correlation data",
                )

        tasks = [
            async_tasks.get_corr_data(
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

                    df[og_name] = pd.Series(data, name=og_name, dtype=int)
                    db.report_progress(current_delta=1)

                await pipe.execute()
        except:
            for t in tasks:
                t.cancel()
            raise


    @db.transaction
    async def tx(pipe: Pipeline):
        pipe.multi()
        pipe.mset({
            f"/tasks/{db.task_id}/stage/{db.stage}/status": "Waiting",
            f"/tasks/{db.task_id}/stage/{db.stage}/message": "",
            f"/tasks/{db.task_id}/stage/{db.stage}/total": 0,
        })
    await tx

    # interpret the results:
    df.fillna(0, inplace=True)
    df.reset_index(drop=False, inplace=True)


    df_for_heatmap = df.copy()
    df_for_heatmap = df_for_heatmap.iloc[:, 1:]
    df_for_heatmap.columns = csv_data['Name']

    tasks = []
    tasks.append(
        asyncio.create_task(
            heatmap(
                db=db,
                organism_count=len(organisms),
                df=df_for_heatmap,
            )
        )
    )
    del df_for_heatmap

    tasks.append(
        asyncio.create_task(
            tree(
                db=db,

                phyloxml_file=phyloxml_file,
                OG_names=csv_data['Name'],
                df=df,
                organisms=organisms,
            )
        )
    )
    del csv_data
    del df
    del organisms

    try:
        await asyncio.gather(*tasks)
        @db.transaction
        async def tx(pipe: Pipeline):
            pipe.multi()
            pipe.set(
                f"/tasks/{db.task_id}/stage/{db.stage}/status", "Done",
            )
        await tx
    except:
        for task in tasks:
            task.cancel()
        raise


# heatmap and tree are very-very similar, but differ just enough to
# duplicate code...
async def heatmap(db: DbClient, **kwargs):
    async def progress(items_in_front):
        if items_in_front > 0:
            msg = f"In queue to build heatmap ({items_in_front} tasks in front)"
        elif items_in_front == 0:
            msg = f"Building heatmap"
        else:
            return

        @db.transaction
        async def tx(pipe: Pipeline):
            pipe.multi()
            pipe.set(
                f"/tasks/{db.task_id}/stage/{db.stage}/heatmap-message",
                msg,
            )
        await tx

    try:
        with (
            atomic_file(db.task_dir / "Correlation.png") as tmp_file,
            atomic_file(db.task_dir / "Correlation_preview.png") as tmp_file2 ):
            task = async_tasks.heatmap(
                **kwargs,
                output_file=tmp_file,
                preview_file=tmp_file2,
            )
            task.set_progress_callback(progress)
            task_res = await task
        to_set = {
            f"/tasks/{db.task_id}/stage/{db.stage}/heatmap-message": "Done",
        }
        if task_res is not None:
            to_set[f"/tasks/{db.task_id}/stage/{db.stage}/heatmap-res"] = task_res
        await redis.mset(to_set)
    except Exception as e:
        msg = f"Error while building heatmap"
        if DEBUG:
            msg += f": {repr(e)}"

        @db.transaction
        async def tx(pipe: Pipeline):
            pipe.multi()
            pipe.set(
                f"/tasks/{db.task_id}/stage/{db.stage}/heatmap-message",
                msg,
            )
        await tx
        raise

    @db.transaction
    async def tx(pipe: Pipeline):
        pipe.multi()
        pipe.set(
            f"/tasks/{db.task_id}/stage/{db.stage}/heatmap-message",
            "Done",
        )
    await tx



async def tree(db: DbClient, **kwargs):
    async def progress(items_in_front):
        if items_in_front > 0:
            msg = f"In queue to build tree ({items_in_front} tasks in front)"
        elif items_in_front == 0:
            msg = f"Building tree"
        else:
            return

        @db.transaction
        async def tx(pipe: Pipeline):
            pipe.multi()
            pipe.set(
                f"/tasks/{db.task_id}/stage/{db.stage}/tree-message",
                msg,
            )
        await tx

    try:
        with atomic_file(db.task_dir / "cluser.xml") as tmp_file:
            task = async_tasks.tree(
                **kwargs,
                output_file=tmp_file,
            )
            task.set_progress_callback(progress)
            task_res = await task
        to_set = {
            f"/tasks/{db.task_id}/stage/{db.stage}/tree-message": "Done",
        }
        if task_res is not None:
            to_set[f"/tasks/{db.task_id}/stage/{db.stage}/tree-res"] = task_res
        await redis.mset(to_set)
    except Exception as e:
        msg = f"Error while building tree"
        if DEBUG:
            msg += f": {repr(e)}"

        @db.transaction
        async def tx(pipe: Pipeline):
            pipe.multi()
            pipe.set(
                f"/tasks/{db.task_id}/stage/{db.stage}/tree-message",
                msg,
            )
        await tx
        raise

    @db.transaction
    async def tx(pipe: Pipeline):
        pipe.multi()
        pipe.set(
            f"/tasks/{db.task_id}/stage/{db.stage}/tree-message",
            "Done",
        )
    await tx

if __name__ == "__main__":
    asyncio.run(main())

