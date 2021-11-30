from ..task_manager import queue_manager
from .prot_search_sync import search_for_prot
from ..task_manager import get_db


@queue_manager.add_handler("/queues/seatch_prot")
async def search_prot(prot_codes, taxid):
    db = get_db()
    try:
        db["prot_search_result"] = await search_for_prot(taxid, prot_codes)
    except Exception:
        db["prot_search_result"] = "# Error while searching for proteins"
        raise
