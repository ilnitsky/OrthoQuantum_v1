import json
from aioredis.client import Pipeline



from . import tree_heatmap_sync

from ..task_manager import get_db
from ..utils import DEBUG, atomic_file, json_minify
from ..redis import enqueue


# heatmap and tree are very-very similar, but differ just enough to
# duplicate code...
async def heatmap(**kwargs):
    async with get_db().substage("heatmap") as db:
        db.msg = "In queue to build heatmap"
        db.total = None
        async def progress(items_in_front):
            # nonlocal db
            if items_in_front > 0:
                db.msg = f"In queue to build heatmap ({items_in_front} tasks in front)"
            elif items_in_front == 0:
                db.msg="Building heatmap"
                await db.sync()

        try:
            with (
                atomic_file(db.task_dir / "Correlation.png") as tmp_file,
                atomic_file(db.task_dir / "Correlation_preview.png") as tmp_file2,
                atomic_file(db.task_dir / "Correlation_table.json") as tmp_file3 ):
                task = tree_heatmap_sync.heatmap(
                    **kwargs,
                    version=db.q_id,
                    output_file=tmp_file,
                    preview_file=tmp_file2,
                    table_file=tmp_file3,

                )
                task.set_progress_callback(progress)
                await task
        except Exception as e:
            msg = f"Error while building heatmap"
            if DEBUG:
                msg += f": {repr(e)}"

            await db.report_error(msg, cancel_rest=False)
            raise
        db["heatmap"] = db.q_id


async def tree(do_blast=False, **kwargs):
    async with get_db().substage("tree") as db:
        db.msg = "In queue to build tree"
        db.total = None
        async def progress(items_in_front):
            if items_in_front > 0:
                db.msg=f"In queue to build tree ({items_in_front} tasks in front)"
            elif items_in_front == 0:
                db.msg = "Building tree"
                await db.sync()

        try:
            with atomic_file(db.task_dir / "tree.xml") as tmp_file:
                task = tree_heatmap_sync.tree(
                    **kwargs,
                    do_blast=do_blast,
                    output_file=tmp_file,
                )
                task.set_progress_callback(progress)
                shape = await task

            # choose presentation method based on shape (squares count)

            info = {
                "kind": "interactive",
                "shape": shape,
                "version": db.q_id,
            }
            #TODO: always svg
            # if shape[0]*shape[1] > 1:
            #     info["kind"] = "svg"

            db["tree"] = json_minify(info)

            # if info["kind"] != "interactive":
            #     # Perform SSR
            #     await enqueue(
            #         version_key=f"/tasks/{db.task_id}/stage/tree/version",
            #         queue_key="/queues/ssr",
            #         queue_id_dest=f"/tasks/{db.task_id}/progress/tree",
            #         queue_hash_key="q_id",
            #         redis_client=pipe,

            #         task_id=db.task_id,
            #         stage="tree",
            #     )


        except Exception as e:
            msg = f"Error while building tree"
            if DEBUG:
                msg += f": {repr(e)}"
            await db.report_error(msg, cancel_rest=False)
            raise

        return shape, info["kind"]

