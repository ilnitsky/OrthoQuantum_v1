import asyncio
from . import tasks as _

from .async_executor import async_pool
from .task_manager import queue_manager
from .redis import redis, GROUP, init_db


@queue_manager.add_handler("/queues/flush_cache")
async def flush_cache(queue_name, q_id, **queue_params):
    async with redis.pipeline(transaction=False) as pipe:
        async for items in redis.scan_iter(match="/cache/*"):
            pipe.delete(items)
        pipe.xack(queue_name, GROUP, q_id)
        await pipe.execute()
    print("Cache flushed")


async def main():
    await init_db()

    async with async_pool, queue_manager:
        await queue_manager()


if __name__ == "__main__":
    asyncio.run(main())
