from distutils import version
from aioredis.client import Pipeline

from . import tree_heatmap_sync, blast

from ..task_manager import DbClient
from ..redis import redis
from ..utils import DEBUG, atomic_file


# heatmap and tree are very-very similar, but differ just enough to
# duplicate code...
async def heatmap(db: DbClient, **kwargs):
    db.report_progress(
        status="Executing",
        message="In queue to build heatmap",
        total=-1,
    )
    async def progress(items_in_front):
        if items_in_front > 0:
            db.report_progress(message=f"In queue to build heatmap ({items_in_front} tasks in front)")
        elif items_in_front == 0:
            await db.flush_progress(message="Building heatmap")

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
            await task
        await db.flush_progress(
            status="Done",
            version=db.version,
        )
    except Exception as e:
        msg = f"Error while building heatmap"
        if DEBUG:
            msg += f": {repr(e)}"

        await db.report_error(msg, cancel_rest=False)
        raise


async def tree(db: DbClient, do_blast=False, **kwargs):
    db.report_progress(
        status="Executing",
        message="In queue to build tree",
        total=-1,
    )
    async def progress(items_in_front):
        if items_in_front > 0:
            db.report_progress(message=f"In queue to build tree ({items_in_front} tasks in front)")
        elif items_in_front == 0:
            await db.flush_progress(message=f"Building tree")

    try:
        with atomic_file(db.task_dir / "cluser.xml") as tmp_file:
            task = tree_heatmap_sync.tree(
                **kwargs,
                do_blast=do_blast,
                output_file=tmp_file,
            )
            task.set_progress_callback(progress)
            leaf_count, to_blast = await task

        # if task_res is not None:
        #     # tree leaf count for display purposes
        #     to_set[f"/tasks/{db.task_id}/stage/{db.stage}/tree-res"] = task_res[0]
        #     to_blast: dict[str, list[int]] = task_res[1] # prot->[taxid]

        @db.transaction
        async def tx(pipe: Pipeline):
            pipe.multi()
            db.report_progress(
                pipe=pipe,
                status="Done",
                version=db.version,
            )
            pipe.set(f"/tasks/{db.task_id}/stage/{db.stage}/leaf_count", leaf_count)
        await tx

    except Exception as e:
        msg = f"Error while building tree"
        if DEBUG:
            msg += f": {repr(e)}"
        await db.report_error(msg, cancel_rest=False)
        raise

    return to_blast

