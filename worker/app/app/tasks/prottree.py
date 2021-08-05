from pathlib import Path
from ..task_manager import queue_manager
from ..redis import redis, GROUP
from .prottree_sync import prottree
from ..utils import DATA_PATH, atomic_file

PROTTREE_DIR = DATA_PATH/'prottrees'
PROTTREE_DIR.mkdir(exist_ok=True)

@queue_manager.add_handler("/queues/prottree")
async def build_prottree(queue_name, q_id, task_id, prot_id):
    error_msg = ''
    try:
        prottree_file = (PROTTREE_DIR/f'{prot_id}.xml')
        with atomic_file(prottree_file) as tmp_path:
            await prottree(prot_id, tmp_path)
    except:
        error_msg = "Error while building the protein tree"
        raise
    finally:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.xack(queue_name, GROUP, q_id)
            pipe.hmset(f"/prottree_tasks/{prot_id}/progress", {
                "status": 'Error' if error_msg else 'Done',
                "message": error_msg,
            })
            await pipe.execute()
