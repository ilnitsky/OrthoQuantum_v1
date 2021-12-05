from ..task_manager import queue_manager
from ..redis import redis
from .prottree_sync import prottree_generator
from ..utils import DATA_PATH, atomic_file

PROTTREE_DIR = DATA_PATH/'prottrees'
PROTTREE_DIR.mkdir(exist_ok=True)

@queue_manager.add_handler("/queues/prottree", raw_data=True)
async def build_prottree(queue_name, q_id, prot_id):
    await redis.hmset(f"/prottree_tasks/{prot_id}/progress", {
        "status": 'Executing',
        "message": "Building gene/protein subfamily tree",
    })

    error_msg = "Error while building the gene/protein subfamily tree"
    try:
        prottree_file = (PROTTREE_DIR/f'{prot_id}.xml')
        with atomic_file(prottree_file) as tmp_path:
            error_msg = await prottree_generator(prot_id, tmp_path)
    except:
        raise
    finally:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.hmset(f"/prottree_tasks/{prot_id}/progress", {
                "status": 'Error' if error_msg else 'Done',
                "message": error_msg,
                "version": q_id,
            })
            await pipe.execute()
