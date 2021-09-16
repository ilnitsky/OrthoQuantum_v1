from ..task_manager import queue_manager
from ..redis import redis, GROUP
from .prot_search_sync import search_for_prot

@queue_manager.add_handler("/queues/seatch_prot")
async def search_prot(queue_name, q_id, task_id, prot_codes, taxid):
    try:
        res = await search_for_prot(taxid, prot_codes)
    except:
        res = "# Error while searching for proteins"
        raise
    finally:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.xack(queue_name, GROUP, q_id)
            pipe.xdel(queue_name, q_id)
            pipe.set(f"/tasks/{task_id}/stage/prot_search/result", res)
            await pipe.execute()
