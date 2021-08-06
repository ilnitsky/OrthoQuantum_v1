import asyncio
from time import time
from datetime import timedelta
import aioredis
from . import tasks as _

from .async_executor import async_pool
from .task_manager import queue_manager
from .redis import redis, GROUP, init_db
from .utils import decode_int


@queue_manager.add_handler("/queues/flush_cache")
async def flush_cache(queue_name, q_id, **queue_params):
    async with redis.pipeline(transaction=False) as pipe:
        async for item in redis.scan_iter(match="/cache/*"):
            pipe.delete(item)
        pipe.xack(queue_name, GROUP, q_id)
        pipe.xdel(queue_name, q_id)
        await pipe.execute()
    print("Cache flushed")


# Delete keys that haven't been accessed in the last 3 months
MAX_CACHE_LIFE_WITHOUT_ACCESS = timedelta(days=30*3).total_seconds()
# Delete cache key after 6 months regardless of access date (to refresh data)
MAX_CACHE_LIFE = timedelta(days=30*6).total_seconds()

async def delete_if_needed(accessed_key:str):
    common_path = accessed_key.rsplit("/", maxsplit=1)[0]
    try:
        async with redis.pipeline(transaction=True) as pipe:
            await pipe.watch(accessed_key)
            last_accessed, created = await pipe.mget(
                accessed_key,
                f"{common_path}/created",
            )
            if not last_accessed or not created:
                return

            last_accessed = decode_int(last_accessed)
            created = decode_int(created)
            cur_time = int(time())

            if (cur_time - last_accessed < MAX_CACHE_LIFE_WITHOUT_ACCESS) and (
                cur_time - created < MAX_CACHE_LIFE
            ):
                return

            keys_to_delete = []

            async for items in pipe.scan_iter(match=f"{common_path}/*"):
                keys_to_delete.append(items)

            pipe.multi()
            pipe.delete(*keys_to_delete)
            await pipe.execute()

    except aioredis.WatchError:
        # update to accessed_key means we should skip this key
        return
    return True


async def clean_cache():
    while True:
        count = 0
        async for item in redis.scan_iter(match="/cache/*/accessed"):
            if await delete_if_needed(item):
                count += 1
        if count:
            print(f"Deleted {count} old cache records")
        # compact the DB every so often
        await redis.bgrewriteaof()
        await asyncio.sleep(timedelta(hours=2).total_seconds()) # run every 2 hours



async def main():
    await init_db()
    await redis.rpush("/worker_initialied", int(time()))
    cache_cleaner = asyncio.create_task(clean_cache())
    try:
        async with async_pool, queue_manager:
            await queue_manager()
    finally:
        cache_cleaner.cancel()
        await redis.delete("/worker_initialied")


if __name__ == "__main__":
    asyncio.run(main())
