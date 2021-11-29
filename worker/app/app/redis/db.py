import asyncio
import os
from pathlib import Path
import json
from itertools import chain
from typing import Optional, Any
from aioredis.client import Pipeline
from lxml import etree as ET
import sqlite3

GROUP = "worker_group"
CONSUMER = "worker_group_consumer"

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}


import aioredis


HOST = os.environ["REDIS_HOST"]

redis = aioredis.from_url(f"redis://{HOST}", encoding="utf-8", decode_responses=True)
raw_redis = aioredis.from_url(f"redis://{HOST}", decode_responses=False)
ORTHODB = "/PANTHERDB/orthodb.db"


LEVELS = {}
TAXID_TO_NAME = {}
_scripts = None

def enqueue(task_id:str, stage:str, params: Optional[dict[str, Any]]=None, redis_client=None, **kwargs):
    if params:
        kwargs.update(params)
    kwargs.setdefault('task_id', task_id)
    kwargs.setdefault('stage', stage)

    if not kwargs:
        raise RuntimeError("empty queue data")
    return _enqueue(
        task_id=task_id,
        stage=stage,
        params=kwargs,
        redis_client=redis_client
    )

def cancel(task_id:str, stage:str, redis_client=None):
    return _enqueue(
        task_id=task_id,
        stage=stage,
        params={},
        redis_client=redis_client
    )

def _enqueue(task_id:str, stage:str, params: dict[str, Any], redis_client=None):
    if redis_client is None:
        redis_client = redis

    return redis_client.evalsha(
        _scripts['enqueue'],
        4,
        f"/queues/{stage}",
        f"/tasks/{task_id}/enqueued",
        f"/tasks/{task_id}/running",
        "/canceled_jobs",

        *chain.from_iterable(params.items()),
        GROUP,
        stage
    )


def report_updates(task_id:str, *updated_keys, redis_client=None):
    if redis_client is None:
        redis_client = redis
    return redis_client.evalsha(
        _scripts['send_updates'],
        2,
        f'/tasks/{task_id}/state/cur_version',
        f'/tasks/{task_id}/state/key_versions',

        *updated_keys
    )


def update(task_id:str, redis_pipe, updates=None, **update):
    """
    performs hset and report_updates
    """
    if updates is not None:
        update.update(updates)
    redis_pipe.hset(f'/tasks/{task_id}/state', mapping=update)
    return report_updates(task_id, *update.keys(), redis_client=redis_pipe)

def happend(key, field, value, separator=None, redis_client=None):
    if redis_client is None:
        redis_client = redis

    if separator is None:
        separator = ()
    else:
        separator = (separator,)

    return redis_client.evalsha(
        _scripts['happend'],
        1,
        key,

        field,
        value,
        *separator
    )

def launch(task_id, stage, q_id, redis_client=None):
    if redis_client is None:
        redis_client = redis

    # -- KEYS[1] - enqueued hash f"/tasks/{task_id}/enqueued"
    # -- KEYS[2] - running hash f"/tasks/{task_id}/running"

    # -- ARGV[1] = stage name
    # -- ARGV[2] = q_id

    return redis_client.evalsha(
        _scripts['launch'],
        2,
        f"/tasks/{task_id}/enqueued",
        f"/tasks/{task_id}/running",

        stage,
        q_id
    )

def finish(task_id, stage, q_id, redis_client=None):
    if redis_client is None:
        redis_client = redis

    # -- KEYS[1] - enqueued hash f"/tasks/{task_id}/enqueued"
    # -- KEYS[2] - running hash f"/tasks/{task_id}/running"

    # -- ARGV[1] = stage name
    # -- ARGV[2] = q_id

    return redis_client.evalsha(
        _scripts['finish'],
        2,
        f"/tasks/{task_id}/enqueued",
        f"/tasks/{task_id}/running",

        stage,
        q_id
    )

def ack(q_name, q_id, redis_pipe: Pipeline):
    redis_pipe.xack(q_name, GROUP, q_id)
    redis_pipe.xdel(q_name, q_id)


async def init_db():
    global _scripts, LEVEL_IDS
    for i in range(30):
        try:
            await redis.ping()
            await raw_redis.ping()
            await redis.delete("/worker_initialied")
            _scripts = await redis.hgetall("/scripts")
            break
        except Exception:
            if i == 9:
                raise
            await asyncio.sleep(1)
    required_scripts = ('enqueue', 'send_updates', 'happend', 'launch', 'finish')
    assert all(s in _scripts for s in required_scripts), 'some script is missing!'

    await init_availible_levels()
    # blocking, but only runs once and fast

def load_level_ids():
    with sqlite3.connect(ORTHODB) as conn:
        res = conn.execute("SELECT scientific_name, level_id FROM levels;")
        data = res.fetchall()

    return {
        k.strip().lower(): v
        for k,v in data
    }


async def init_availible_levels():
    global LEVELS
    level_ids = load_level_ids()
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
        try:
            level_orthodb_id = level_ids[level.strip().lower()]
        except KeyError:
            raise RuntimeError(f"Can't find orthodb level id for {level}")

        l.append(
            (
                int(id),
                level,
                level_orthodb_id,
                name,
                str(file.resolve()),
            )
        )

    l.sort()

    parser = ET.XMLParser(remove_blank_text=True)

    async with redis.pipeline(transaction=False) as pipe:
        availible_levels = {}
        for id, level, orthodb_id, name, path in l:
            LEVELS[id] = (level, orthodb_id, path)
            availible_levels[name] = id

            # options for the gene search dropdown

            tree = ET.parse(path, parser)
            root = tree.getroot()

            orgs_xml = root.xpath("//pxml:id/..", namespaces={'pxml':"http://www.phyloxml.org"})
            # Assuming only children have IDs
            orgs = []
            for org_xml in orgs_xml:
                try:
                    taxid = int(org_xml.find("id", NS).text)
                    name = org_xml.find("name", NS).text
                    orgs.append({
                        'label': name,
                        'value': taxid,
                    })
                    TAXID_TO_NAME[taxid] = name

                except Exception:
                    # org_id contains letters, this could happen for missing organism
                    pass
            orgs.sort(key=lambda x: x['label'])
            pipe.set(f"/availible_levels/{id}/search_dropdown", json.dumps(orgs))


        pipe.set("/availible_levels", json.dumps(availible_levels))

        await pipe.execute()
