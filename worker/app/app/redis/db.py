import asyncio
import os
from pathlib import Path
import json


import aioredis


HOST = os.environ["REDIS_HOST"]

redis = aioredis.from_url(f"redis://{HOST}", encoding="utf-8", decode_responses=True)
LEVELS = {}

async def init_db():
    global redis
    redis = aioredis.from_url(f"redis://{HOST}", encoding="utf-8", decode_responses=True)
    for i in range(10):
        try:
            await redis.ping()
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

    availible_levels = {}
    for id, level, name, path in l:
        LEVELS[id] = (level, path)
        availible_levels[name] = id

    await redis.set("/availible_levels", json.dumps(availible_levels))
