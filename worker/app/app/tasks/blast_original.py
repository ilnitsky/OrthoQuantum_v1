# blast using blastp
import asyncio
from tempfile import NamedTemporaryFile
from collections import defaultdict
import io
from typing import Optional
import aiohttp
import time

import numpy as np
import pandas as pd
from aioredis.client import Pipeline
from lxml import etree as ET

from ..task_manager import get_db, queue_manager
from ..utils import atomic_file
from ..redis import raw_redis, enqueue
from . import blast_sync

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}
NS_XPATH = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "pxml": "http://www.phyloxml.org",
}

COLS = (
    'evalue',
    'pident',
    'qcovs'
)

@queue_manager.add_handler("/queues/blast", max_running=3)
async def blast(blast_autoreload=False, enqueue_tree_gen=False):
    db = get_db()
    db.msg = "Getting blast data"
    @db.transaction
    async def res(pipe:Pipeline):
        pipe.multi()
        pipe.mget(
            f"/tasks/{db.task_id}/request/blast_evalue",
            f"/tasks/{db.task_id}/request/blast_pident",
            f"/tasks/{db.task_id}/request/blast_qcovs",
        )

    evalue, pident, qcovs = (await res)[-1]
    evalue = -np.log10(float(evalue))
    pident = float(pident)
    qcovs = float(qcovs)

    user_cond = pd.Series(
        {
            'evalue': evalue,
            'pident': pident,
            'qcovs': qcovs,
        },
        dtype=np.float64
    )


    blast_request, name_2_prot, name_to_idx, tree, tree_root = await blast_sync.load_data(
        phyloxml_file=str(db.task_dir / "tree.xml"),
        og_file=str(db.task_dir / "OG.csv"),
    )
    blast_request:dict[str, list[int]] # "Name" list[tax_id]
    name_2_prot:dict[str, str] # "Name" -> "UniProt_AC"
    name_to_idx:dict[str, int]
    tree: ET.ElementTree #- ET eltree (.getroot() needed)
    tree_root: ET.Element

    blasted:dict[str, dict[int, Optional[pd.DataFrame]]] = defaultdict(dict) # "Name" dict[tax_id, float_blast_val]

    prots: defaultdict[str, list[str]] = defaultdict(list) #  "UniProt_AC" -> list["Name"]
    for name in blast_request.keys():
        prots[name_2_prot[name]].append(name)



    # load_bytes = BytesIO(np_bytes)
    # loaded_np = np.load(load_bytes, allow_pickle=True)

    # requesting cache:
    cur_time = int(time.time())
    cache = {}
    async with raw_redis.pipeline(transaction=False) as pipe:
        for prot, names in prots.items():
            cache[prot] = set()
            for name in names:
                cache[prot].update(blast_request[name])
            cache[prot] = tuple(cache[prot])

            pipe.mget(
                f"/cache/blast/{prot}/{tax_id}/data"
                for tax_id in cache[prot]
            )
        for prot, data in cache.items():
            for tax_id in data:
                pipe.set(f"/cache/blast/{prot}/{tax_id}/accessed", cur_time, xx=True)
        cache_req_res = await pipe.execute()
    for prot, cache_res in zip(cache, cache_req_res):
        cache[prot] = dict(zip(cache[prot], cache_res)) # None if missing, b'' if blast did not found anything, numpy arr if blast found stuff

    to_blast:defaultdict[str, list[int]] = defaultdict(list)
    for prot, names in prots.items():
        for name in names:
            for tax_id in blast_request[name]:
                cache_data = cache[prot][tax_id]
                if cache_data is None:
                    to_blast[name].append(tax_id)
                elif not cache_data:
                    blasted[name][tax_id] = None # blast did not find anything at all last time
                else:
                    # got a saved numpy array, parse as a df
                    memfile = io.BytesIO(cache_data)
                    blasted[name][tax_id] = pd.DataFrame(
                        np.load(memfile),
                        columns=COLS,
                    )
            await asyncio.sleep(0)

    prots_to_fetch = {
        name_2_prot[name] for name in to_blast
    }
    db.current = 0
    db.total = len(prots_to_fetch)
    db.msg = "Getting sequences"

    prot_seq: dict[str, str] = {} # UniProt_AC -> fasta data


    async def fetch(session:aiohttp.ClientSession):
        while prots_to_fetch:
            prot = prots_to_fetch.pop()
            async with session.get(f"http://www.uniprot.org/uniprot/{prot}.fasta") as resp:
                prot_seq[prot] = await resp.text()
                db.current += 1

    max_parallel_fetches = 4

    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(fetch(session))
            for _ in range(max_parallel_fetches)
        ]
        try:
            await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()

    db.current = 0
    db.total = len(to_blast)
    db.msg = "BLASTing"


    render_cond = asyncio.Condition()
    to_blast_iter = iter(to_blast)

    async def blast_task_func():
        for name in to_blast_iter:
            tax_ids = to_blast[name]
            prot = name_2_prot[name]
            prot_fasta = prot_seq[prot]
            with NamedTemporaryFile("r", suffix=".blast_result.csv") as res_f:
                with (NamedTemporaryFile("w", suffix=".req_file.fa") as req_f,
                    NamedTemporaryFile("w", suffix=".taxids") as taxids_f):

                    await blast_sync.write_blast_files(req_f, prot_fasta, taxids_f, tax_ids)
                    proc = await asyncio.create_subprocess_exec(
                        "blastp",
                        "-query", req_f.name,
                        "-taxidlist", taxids_f.name,
                        "-out", res_f.name,
                        "-db", "/blast/blastdb/nr.00",
                        "-evalue", "1e-3", # the system relies on E < 1 (because we're using log).
                        "-max_target_seqs", "2000",
                        "-outfmt", f"10 {' '.join(blast_sync.COLS.keys())}",
                        "-num_threads", "4",

                    )
                    try:
                        return_code = await proc.wait()
                    except asyncio.CancelledError:
                        proc.kill()
                        raise

                if return_code != 0:
                    await db.report_error("Unknown blast error")
                    return

                res = await blast_sync.process_blast_data(res_fn=res_f.name)
                res: dict[int, pd.DataFrame]

            cur_blasted = {}
            async with raw_redis.pipeline(transaction=False) as pipe:
                memfile = io.BytesIO()
                cur_time = int(time.time())
                for tax_id in tax_ids:
                    df = res.get(tax_id)
                    cur_blasted[tax_id] = df
                    if df is not None:
                        np.save(memfile, df.to_numpy())
                        memfile.truncate()
                        memfile.seek(0)
                        store_bytes = memfile.read()
                        memfile.seek(0)
                    else:
                        store_bytes = b''
                    pipe.mset(
                        {
                            f"/cache/blast/{prot}/{tax_id}/data": store_bytes,
                            f"/cache/blast/{prot}/{tax_id}/accessed": cur_time,
                        },
                    )
                    pipe.setnx(f"/cache/blast/{prot}/{tax_id}/created", cur_time)
                    await asyncio.sleep(0)
                await pipe.execute()

            async with render_cond:
                blasted[name] = cur_blasted
                render_cond.notify_all()
            db.current += 1

    max_running_blasts = 2
    blast_tasks = [
        asyncio.create_task(blast_task_func())
        for _ in range(max_running_blasts)
    ]

    async def render_tree():
        nonlocal blasted, blast_tasks
        heatmap_data = tree_root.find('.//graphs/graph/data', NS)
        while True:
            async with render_cond:
                await render_cond.wait_for(lambda: blasted or (blast_tasks is None))
                if blast_tasks is None and not blasted:
                    # we're finished
                    @db.transaction
                    async def res(pipe:Pipeline):
                        pipe.multi()
                        if enqueue_tree_gen:
                            await enqueue(
                                version_key=f"/tasks/{db.task_id}/stage/tree/version",
                                queue_key="/queues/ssr",
                                queue_id_dest=f"/tasks/{db.task_id}/progress/tree",
                                queue_hash_key="q_id",
                                redis_client=pipe,

                                task_id=db.task_id,
                                stage="tree",
                            )
                            pipe.hset(f"/tasks/{db.task_id}/progress/tree",
                                mapping={
                                    "status": 'Enqueued',
                                    'total': -1,
                                    "message": "Re-rendering",
                                }
                            )
                        elif not blast_autoreload:
                            # trigger tree reload
                            # incr by 1_000_000 to avoid messing up with anti-cache things...
                            pipe.hincrby(f"/tasks/{db.task_id}/progress/tree", "version", 1_000_000)
                    await res
                    return
                tree_upd = blasted
                blasted = {}
            # update tree with tree_upd data
            # /values

            for name, data in tree_upd.items():
                idx = name_to_idx[name]+1
                for tax_id, df in data.items():
                    el = heatmap_data.xpath(f"(./pxml:values[@for='{tax_id}']/pxml:value)[{idx}]", namespaces=NS_XPATH)[0]
                    if df is not None and (df>user_cond).all(axis=1).any():
                        # at least one thing found, report pos
                        el.text = "62" # 50+12
                    else:
                        # no blast matches, confirm not found
                        el.text = "37" # 25+12
                await asyncio.sleep(0)
            with atomic_file(db.task_dir / "tree.xml") as tmp_name:
                await blast_sync.write_tree(tmp_name, tree)
                await db.check_if_cancelled()
                # minimal race condition window before last command and writing the tree file
                # shouldn't give us any trouble
            if blast_autoreload and not enqueue_tree_gen:
                @db.transaction
                async def res(pipe:Pipeline):
                    pipe.multi()
                    # trigger tree reload
                    # incr by 1_000_000 to avoid messing up with anti-cache things...
                    pipe.hincrby(f"/tasks/{db.task_id}/progress/tree", "version", 1_000_000)
                await res

    render_task = asyncio.create_task(render_tree())
    try:
        await asyncio.wait(blast_tasks, return_when=asyncio.ALL_COMPLETED)
        async with render_cond:
            blast_tasks = None
            render_cond.notify_all()
        await render_task
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        render_task.cancel()
        raise
