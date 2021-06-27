import asyncio
import os
from pathlib import Path
import json
from itertools import chain
from typing import Optional, Any
from lxml import etree as ET

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}


import aioredis


HOST = os.environ["REDIS_HOST"]

redis = aioredis.from_url(f"redis://{HOST}", encoding="utf-8", decode_responses=True)
raw_redis = aioredis.from_url(f"redis://{HOST}", decode_responses=False)

LEVELS = {}
TAXID_TO_NAME = {}


_enqueue_script = redis.register_script("""
    -- KEYS[1] - version
    -- KEYS[2] - queue
    -- KEYS[3] - queue_id_dest (empty string to skip)

    -- ARGV - kv pairs to add to the queue (leave empty to only cancel)

    local version = redis.call('incr', KEYS[1])
    local hkey = table.remove(ARGV)
    local queue_id = nil
    if (KEYS[3] ~= '') then
        if (hkey == '') then
            queue_id = redis.call('get', KEYS[3])
        else
            queue_id = redis.call('hget', KEYS[3], hkey)
        end
        redis.call('del', KEYS[3])
    end

    if (queue_id and queue_id ~= '') then
        redis.call('xdel', KEYS[2], queue_id)
    end

    -- enqueue
    if #ARGV ~= 0 then
        queue_id = redis.call('xadd', KEYS[2], '*', 'version', version, unpack(ARGV))
        if (KEYS[3] ~= '') then
            if (hkey == '') then
                redis.call('set', KEYS[3], queue_id)
            else
                redis.call('hset', KEYS[3], hkey, queue_id)
            end
        end
    end
    return {version, queue_id}

""")

def enqueue(version_key, queue_key, queue_id_dest=None, queue_hash_key=None, params: Optional[dict[str, Any]]=None, redis_client=None, **kwargs):
    if params:
        kwargs.update(params)
    args = list(chain.from_iterable(kwargs.items()))
    if not args:
        raise RuntimeError("empty queue data")
    args.append(queue_hash_key or '')
    return _enqueue_script(
        keys=(
            version_key,
            queue_key,
            queue_id_dest or '',
        ),
        args=args,
        client=redis_client,
    )


async def init_db():
    for i in range(10):
        try:
            await redis.ping()
            await raw_redis.ping()
            break
        except Exception:
            if i == 9:
                raise
            await asyncio.sleep(1)
    await init_availible_levels()









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

    parser = ET.XMLParser(remove_blank_text=True)

    async with redis.pipeline(transaction=False) as pipe:
        availible_levels = {}
        for id, level, name, path in l:
            LEVELS[id] = (level, path)
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
