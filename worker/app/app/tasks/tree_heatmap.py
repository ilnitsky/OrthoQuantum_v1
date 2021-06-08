from aioredis.client import Pipeline

from . import tree_heatmap_sync, blast

from ..task_manager import DbClient
from ..redis import redis
from ..utils import DEBUG, atomic_file


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
            task = tree_heatmap_sync.heatmap(
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



async def tree(db: DbClient, do_blast=False, **kwargs):
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
            task = tree_heatmap_sync.tree(
                **kwargs,
                do_blast=do_blast,
                output_file=tmp_file,
            )
            task.set_progress_callback(progress)
            task_res = await task
        to_set = {
            f"/tasks/{db.task_id}/stage/{db.stage}/tree-message": "Done",
        }
        if task_res is not None:
            # tree leaf count for display purposes
            to_set[f"/tasks/{db.task_id}/stage/{db.stage}/tree-res"] = task_res[0]
            to_blast: dict[str, list[int]] = task_res[1] # prot->[taxid]

        @db.transaction
        async def tx(pipe: Pipeline):
            pipe.multi()
            pipe.mset(to_set)
        await tx

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

    return to_blast

