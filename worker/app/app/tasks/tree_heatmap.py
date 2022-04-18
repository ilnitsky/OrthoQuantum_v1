from typing import Optional
from aioredis.client import Pipeline

from . import tree_heatmap_sync

from ..task_manager import get_db
from ..utils import DEBUG, json_minify
from ..redis import enqueue, update


# heatmap and tree are very-very similar, but differ just enough to
# duplicate code...
async def heatmap(organism_count, df, max_prots=0) -> Optional[set[str]]:
    res = None
    async with get_db().substage("heatmap") as db:
        if df.shape[1] < 2:
            await db.report_error("Not enough proteins to build the correlation matrix", cancel_rest=False)
            return
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
            async with  (
                db.atomic_file(db.task_dir / "Correlation.png") as tmp_file,
                db.atomic_file(db.task_dir / "Correlation_preview.png") as tmp_file2,
                db.atomic_file(db.task_dir / "Correlation_table.pkl") as tmp_file3 ):
                task = tree_heatmap_sync.heatmap(
                    organism_count=organism_count,
                    df=df,

                    output_file=tmp_file,
                    preview_file=tmp_file2,
                    table_file=tmp_file3,
                    max_prots=max_prots,
                )
                task.set_progress_callback(progress)
                res = await task
        except Exception as e:
            msg = f"Error while building heatmap"
            if DEBUG:
                msg += f": {repr(e)}"

            await db.report_error(msg, cancel_rest=False)
            raise
        db["heatmap"] = db.q_id
    return res







async def tree(do_blast, phyloxml_file, OG_names, df, prot_ids):
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
            async with db.atomic_file(db.task_dir / "tree.xml") as tmp_file:
                task = tree_heatmap_sync.tree(
                    phyloxml_file=phyloxml_file,
                    OG_names=OG_names,
                    df=df,
                    prot_ids=prot_ids,

                    do_blast=do_blast,
                    output_file=tmp_file,
                )
                task.set_progress_callback(progress)
                shape = await task

            # choose presentation method based on shape (squares count)

            info = {
                "kind": "interactive",
                "shape": shape,
            }
            #TODO: always svg
            # if shape[0]*shape[1] > 1:
            #     info["kind"] = "svg"

            db["tree"] = json_minify(info)
            db["tree_version"] = db.q_id

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
            if do_blast:
                @db.transaction
                async def res(pipe: Pipeline):
                    pipe.multi()
                    update(db.task_id, redis_pipe=pipe,
                        progress_blast_msg="BLASTing",
                        progress_blast_total="",
                    )

                    await enqueue(
                        task_id=db.task_id,
                        stage="blast",
                        redis_client=pipe,

                        blast_autoreload="1" if shape[0]*shape[1]<80_000 else "",
                        enqueue_tree_gen="1" if info["kind"]!="interactive" else "",
                    )
                await res


        except Exception as e:
            msg = f"Error while building tree"
            if DEBUG:
                msg += f": {repr(e)}"
            await db.report_error(msg, cancel_rest=False)
            raise


