import asyncio
from functools import partial, wraps
from collections import defaultdict, deque
import io
import traceback
from typing import Optional
import time
import re

import json
import hashlib

import numpy as np
import pandas as pd
from aioredis.client import Pipeline
from lxml import etree as ET
import httpx

from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..task_manager import get_db, queue_manager, ReportErrorException, DbClient
from ..utils import atomic_file
from ..redis import raw_redis, redis, enqueue, report_updates
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


DELAY_RE = re.compile(rb'var tm = "(\d+)"')
SUGGEST_RE = re.compile(rb'new Array\("([^@]+)')
PROT_CODE_RE = re.compile(r'sp\|([A-Z0-9]+)')

MAX_ATTEMPTS = 12
MAX_ELAPSED = "00:30:00" # max time a request can chill in NCBI waitng screen
MAX_NCBI_STATUS_REFRESHES = 1000

COLS = {
    'evalue': np.float64,
    'pident': np.float64,
    'qcov'  : np.float64,
    'id'    : pd.StringDtype(),
}
USER_REQ_COLS = list(COLS.keys())[:-1]

class RequestTooLargeException(Exception): pass

def retry(func=None, max_delay_length=60, start_delay=0.1):
    if func is None:
        return partial(retry, max_delay_length=max_delay_length, start_delay=start_delay)
    else:
        @wraps(func)
        async def repeater(*args, **kwargs):
            delay = start_delay
            for attempt in range(1, MAX_ATTEMPTS+1):
                try:
                    return await func(*args, **kwargs)
                except ReportErrorException:
                    raise
                except Exception as e:
                    if attempt == MAX_ATTEMPTS:
                        raise ReportErrorException("Retry limit exceeded") from e
                    print(f"Request retry #{attempt}, exception:")
                    traceback.print_exc()
                    await asyncio.sleep(delay)
                    if delay<max_delay_length:
                        delay = min(delay * 2, max_delay_length)
        return repeater

async def do_blast_request(sess:httpx.Client, prot_list, organisms):
    """performs one search and extracts the data for all proteins"""
    request_data = {
        "ADV_VIEW": "on",
        "ALIGNMENT_VIEW": "Pairwise",
        "ALIGNMENTS": "100",
        "BLAST_PROGRAMS": "blastp",
        "BLAST_SPEC": "",
        "CDD_SEARCH": "on",
        "CHECKSUM": "",
        "CLIENT": "web",
        "CMD": "request",
        "COMPOSITION_BASED_STATISTICS": "2",
        "CONFIG_DESCR": "2,3,6,7,8,9,10,11,12",
        "DATABASE": "nr",
        "DB_DIR_PREFIX": "",
        "DB_DISPLAY_NAME": "nr",
        "db": "protein",
        "DESCRIPTIONS": "5000",
        "DI_THRESH": "",
        "EQ_TEXT": "",
        "EXPECT_HIGH": "",
        "EXPECT_LOW": "",
        "EXPECT": "0.00000001",
        "FORMAT_EQ_TEXT": "",
        "FORMAT_NUM_ORG": "1",
        "FORMAT_OBJECT": "Alignment",
        "FORMAT_ORGANISM": "",
        "FORMAT_TYPE": "HTML",
        "GAPCOSTS": "11 1",
        "GENETIC_CODE": "1",
        "GET_SEQUENCE": "on",
        "HSP_RANGE_MAX": "0",
        "I_THRESH": "",
        "ID_FOR_PSSM": "",
        "LINE_LENGTH": "60",
        "MASK_CHAR": "2",
        "MASK_COLOR": "1",
        "MATCH_SCORES": "1,-2",
        "MATRIX_NAME": "BLOSUM62",
        "MAX_NUM_SEQ": "5000", # Max items to find
        "MEGABLAST": "",
        "MIXED_DATABASE": "",
        "NCBI_GI": "",
        "NEW_VIEW": "on",
        "NO_COMMON": "",
        "NUM_DIFFS": "2",
        "NUM_OPTS_DIFFS": "2",
        "NUM_OVERVIEW": "100",
        "ORG_DBS": "giless_dbvers5",
        "PAGE_TYPE": "BlastSearch",
        "PAGE": "Proteins",
        "PERC_IDENT_HIGH": "",
        "PERC_IDENT_LOW": "",
        "PHI_PATTERN": "",
        "PROGRAM": "blastp",
        "PSI_PSEUDOCOUNT": "",
        "QUERY_BELIEVE_DEFLINE": "",
        "QUERY_FROM": "",
        "QUERY_INDEX": "0",
        "QUERY_TO": "",
        "REPEATS": "566037",
        "RUN_PSIBLAST": "",
        "SAVED_PSSM": "",
        "SAVED_SEARCH": "",
        "SELECTED_PROG_TYPE": "blastp",
        "SERVICE": "plain",
        "SHORT_QUERY_ADJUST": "on",
        "SHOW_CDS_FEATURE": "",
        "SHOW_LINKOUT": "on",
        "SHOW_OVERVIEW": "on",
        "stype": "protein",
        "SUBJECTS_FROM": "",
        "SUBJECTS_TO": "",
        "SUBJECTS": "",
        "TEMPLATE_LENGTH": "0",
        "TEMPLATE_TYPE": "0",
        "TWO_HITS": "",
        "UNIQ_DEFAULTS_NAME": "",
        "USER_DATABASE": "",
        "USER_DEFAULT_MATRIX": "4",
        "USER_DEFAULT_PROG_TYPE": "blastp",
        "USER_FORMAT_DEFAULTS": "",
        "USER_MATCH_SCORES": "",
        "USER_WORD_SIZE": "",
        "WORD_SIZE": "6",
        "WWW_BLAST_TYPE": "",
    }

    request_data["NUM_ORG"] = str(len(organisms))
    request_data["EQ_MENU"] = organisms[0]
    for i, org_name in enumerate(organisms[1:], 1):
        request_data[f"EQ_MENU{i}"] = org_name

    request_data["QUERY"] = '\n'.join(prot_list)
    request_data["JOB_TITLE"] = f"Blast search job for {';'.join(prot_list)}"

    # request continuation mechanism:
    req_hash = hashlib.sha256(json.dumps(request_data, sort_keys=True).encode()).hexdigest()

    from_cache = False
    deleter = None
    try:
        ncbi_request_id = await redis.get(f"/cache/ongoing_blast_requests/{req_hash}")

        if ncbi_request_id:
            # get the page from results
            resp = await retry(sess.get)(
                "https://blast.ncbi.nlm.nih.gov/Blast.cgi",
                params={
                    "RID": ncbi_request_id,
                    "CMD": "Get",
                }
            )
            from_cache = True
            deleter = ncbi_delete_req(None, ncbi_request_id, req_hash)
            print(f"Request continuation on {ncbi_request_id}")
        else:
            # Send request
            resp = await retry(sess.post)("https://blast.ncbi.nlm.nih.gov/Blast.cgi",
                data=request_data,
                files={
                    'QUERYFILE': ('', b'', 'application/octet-stream'),
                    'SUBJECTFILE': ('', b'', 'application/octet-stream'),
                    'PSSM': ('', b'', 'application/octet-stream'),
                },
            )

        # Update status
        for req_no in range(MAX_NCBI_STATUS_REFRESHES):
            soup = BeautifulSoup(resp.content, 'html.parser')

            # Check errors
            error_list = soup.select("ul.msg.error")
            if error_list:
                print(error_list)
                error_list = error_list[0]
                errors = error_list.find_all("li")
                if errors:
                    error_msgs = [
                        error.get_text().strip()
                        for error in errors
                    ]
                else:
                    error_msgs = ["Unknown error"]
                error_msg = '; '.join(error_msgs)
                if "CPU usage limit was exceeded" in error_msg:
                    raise RequestTooLargeException()
                raise RuntimeError(error_msg)

            # Get wait data
            table = soup.find("table", id="statInfo")
            if not table:
                # probably finished
                break

            # extract parameters form the page
            form = soup.find("div", id="content").find("form")
            params={
                inp['name']: inp['value']
                for inp in form.find_all("input")
            }

            if not from_cache and req_no == 0:
                ncbi_request_id = params["RID"].strip()
                deleter = ncbi_delete_req(sess, ncbi_request_id, req_hash)
                await redis.set(
                    f"/cache/ongoing_blast_requests/{req_hash}",
                    ncbi_request_id,
                    ex=24*60*60, # 1 day, less than ncbi expiery
                )

            # extract delay from the page
            delay_match = DELAY_RE.search(resp.content)
            if delay_match:
                delay = int(delay_match.group(1))//1000
            else:
                if req_no == 0:
                    delay = 1
                else:
                    print("can't find delay")
                    delay = 10
            delay = max(delay, 1)

            rows = table.find_all("tr")
            status = rows[1].find_all("td")[-1].get_text().strip()
            elapsed = rows[-1].find_all("td")[-1].get_text().strip()
            if elapsed > MAX_ELAPSED:
                raise RuntimeError(f"Request takes more than {MAX_ELAPSED}")

            print(
                f'Blast request {ncbi_request_id}: '
                f'status: {status}; '
                f'elapsed: {elapsed}; '
                f'refresh in: {delay}'
            )
            await asyncio.sleep(delay)

            resp = await retry(sess.post)(
                "https://blast.ncbi.nlm.nih.gov/Blast.cgi",
                data=urlencode(params),
            )
        else:
            # no break -> 1000 requests without result
            raise RuntimeError(f"Request took over {MAX_NCBI_STATUS_REFRESHES}")

        # search finished, parsing results
        prot_2_data = {}
        prot_pages = []

        for opt in soup.find(id="queryList").find_all("option"):
            match = PROT_CODE_RE.search(opt.text)

            if not match:
                continue
            prot_id = match.group(1)

            if 'nohits' in opt.attrs.get('class', ''):
                # empty page
                continue

            if 'selected' in opt.attrs:
                prot_2_data[prot_id], params = await blast_sync.extract_table_data(resp.content)
                del resp
            else:
                prot_pages.append((prot_id, opt.attrs["value"]))

        del soup, opt

        for prot_id, opt_id in prot_pages:
            # choosing next item from the list
            params["QUERY_INDEX"] = opt_id
            # max rows for the table
            params["DESCRIPTIONS"] = "5000"

            # Send request
            resp = await retry(sess.post)(
                "https://blast.ncbi.nlm.nih.gov/Blast.cgi",
                data=urlencode(params),
            )
            prot_2_data[prot_id], params = await blast_sync.extract_table_data(resp.content)


        # delete result to be nice to ncbi

        # fill any missing proteins from request (empty pages or errors(?))
        for prot in prot_list:
            if prot not in prot_2_data:
                prot_2_data[prot] = {}

    except Exception:
        await deleter
        raise
    return prot_2_data, deleter




async def ncbi_delete_req(sess:httpx.Client, req_id, req_hash):
    try:
        await redis.delete(f"/cache/ongoing_blast_requests/{req_hash}")
        if sess is None:
            return
        res = await retry(sess.get)("https://blast.ncbi.nlm.nih.gov/Blast.cgi?CMD=GetSaved&RECENT_RESULTS=on")
        soup = BeautifulSoup(res.content, 'html.parser')
        table = soup.find("div", id="content").find("table")
        for row in table.find_all("tr")[1:]:
            tds = row.find_all("td")
            rid = tds[1].text.strip()
            if rid == req_id:
                del_link = row.find("a", class_="del")
                await retry(sess.get)(f'https://blast.ncbi.nlm.nih.gov/{del_link.attrs["href"]}')
                break
    except Exception:
        # best-effort task, swallowing exceptions
        print("Error while deleting the request (non-critical)")
        traceback.print_exc()


async def get_ncbi_taxids_from_cache(taxids_to_get):
    if not taxids_to_get:
        return {}
    taxids_to_get_list = list(taxids_to_get)
    values = await redis.hmget("/cache/taxids-for-blast", taxids_to_get_list)

    res = {}
    for taxid, org_name in zip(taxids_to_get_list, values):
        if org_name is None:
            continue
        if isinstance(org_name, bytes):
            org_name = org_name.decode()
        res[taxid] = org_name
    return res


async def blast_request_task(sess:httpx.AsyncClient, prot_chunk:list[str], taxids_to_request:set[int], organisms_to_request:list[str], prots_to_get:dict[str, set[int]]):
    if not (prot_chunk and taxids_to_request):
        return {}
    prot_chunk.sort()
    res, deleter = await do_blast_request(
        sess, prot_chunk,
        organisms_to_request,
    )
    try:
        blasted = defaultdict(dict)
        async with raw_redis.pipeline(transaction=False) as pipe:
            memfile = io.BytesIO()
            cur_time = int(time.time())
            for prot, taxid_data in res.items():
                for tax_id in prots_to_get[prot].intersection(taxids_to_request):
                    df = taxid_data.get(tax_id)
                    blasted[prot][tax_id] = df
                    if df is not None:
                        store_bytes = df.to_csv(header=False, index=False)[:-1].encode()
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
    finally:
        await deleter

    return blasted

class TreeRenderer():
    def __init__(self, db, tree, prots, name_to_idx, name_to_prot, user_cond, blast_request, enqueue_tree_gen) -> None:
        self.current_data = {}
        self.renderer_task: asyncio.Task = None

        self.tree = tree
        self.tree_root = tree.getroot()
        self.prots = prots
        self.name_to_idx = name_to_idx
        self.name_to_prot = name_to_prot
        self.user_cond = user_cond
        self.db: DbClient = db
        self.blast_request = blast_request
        self.enqueue_tree_gen = enqueue_tree_gen

    def render(self, new_data, render_now=True):
        self.current_data.update(new_data)
        if self.renderer_task:
            self.renderer_task.cancel()
        if render_now:
            self.renderer_task = asyncio.create_task(self._renderer())
            self.renderer_task.add_done_callback(self._current_clearer)
            return self.renderer_task


    def _current_clearer(self, task:asyncio.Task):
        self.renderer_task = None

    async def _renderer(self):
        heatmap_data = self.tree.getroot().find('.//graphs/graph/data', NS)
        for name, taxids in self.blast_request.items():
            prot_id = self.name_to_prot[name]
            if prot_id not in self.current_data:
                continue
            idx = self.name_to_idx[name]+1
            for tax_id in taxids:
                df = self.current_data[prot_id].get(tax_id)
                el = heatmap_data.xpath(f"(./pxml:values[@for='{tax_id}']/pxml:value)[{idx}]", namespaces=NS_XPATH)[0]
                if df is not None:
                    df = df[
                        (df[USER_REQ_COLS]>=self.user_cond).all(axis=1)
                    ]
                    if df.empty:
                        df = None
                if df is not None:
                    # TODO: add protein/species name to the tooltip
                    # (used to do it in JS, no longer sensible)

                    # at least one thing found, report pos
                    el.text = "62" # 50+12
                    el.attrib['label'] = "BLAST: "+(df["id"].str.cat(sep=";"))
                else:
                    # no blast matches, confirm not found
                    el.text = "37" # 25+12
                    try:
                        del el.attrib['label']
                    except KeyError:
                        pass
            await asyncio.sleep(0)
        with atomic_file(self.db.task_dir / "tree.xml") as tmp_name:
            await blast_sync.write_tree(tmp_name, self.tree)
            await self.db.check_if_cancelled()
            # minimal race condition window before last command and writing the tree file
            # shouldn't give us any trouble

        @self.db.transaction
        async def res(pipe:Pipeline):
            pipe.multi()
            pipe.hincrby(self.db.state_key, "tree_blast_ver")
            report_updates(self.db.task_id, "tree", "tree_blast_ver", redis_client=pipe)
        await res

    async def flush(self):
        await self.render({})




@queue_manager.add_handler("/queues/blast", max_running=3)
async def blast(blast_autoreload=False, enqueue_tree_gen=False):
    db = get_db()
    db.current = 0
    db.msg = "Getting blast data"
    data = await db[
        "input_blast_evalue",
        "input_blast_pident",
        "input_blast_qcovs",
    ]
    user_cond = pd.Series(
        dict(zip(
            USER_REQ_COLS,
            (
                -np.log10(float(data[0])),
                float(data[1]),
                float(data[2]),
            )
        )),
        dtype=np.float64
    )

    blast_request, name_to_prot, name_to_idx, tree = await blast_sync.load_data(
        phyloxml_file=str(db.task_dir / "tree.xml"),
        og_file=str(db.task_dir / "OG.csv"),
    )
    blast_request:dict[str, list[int]] # "Name" list[tax_id]
    name_to_prot:dict[str, str] # "Name" -> "UniProt_AC"
    name_to_idx:dict[str, int] # "Name" -> column #
    tree: ET.ElementTree #- ET eltree (.getroot() needed)

    parsed_cache: dict[str, dict[int, Optional[pd.DataFrame]]] = defaultdict(dict) # "Name" dict[tax_id, float_blast_val]

    prots: defaultdict[str, list[str]] = defaultdict(list) #  "UniProt_AC" -> list["Name"]
    for name in blast_request.keys():
        prots[name_to_prot[name]].append(name)

    # requesting cache:
    cur_time = int(time.time())
    raw_cache = {}
    async with raw_redis.pipeline(transaction=False) as pipe:
        for prot, names in prots.items():
            raw_cache[prot] = set()
            for name in names:
                raw_cache[prot].update(blast_request[name])
            raw_cache[prot] = tuple(raw_cache[prot])

            pipe.mget(
                f"/cache/blast/{prot}/{tax_id}/data"
                for tax_id in raw_cache[prot]
            )
        for prot, data in raw_cache.items():
            for tax_id in data:
                pipe.set(f"/cache/blast/{prot}/{tax_id}/accessed", cur_time, xx=True)
        cache_req_res = await pipe.execute()
    for prot, cache_res in zip(raw_cache, cache_req_res):
        raw_cache[prot] = dict(zip(raw_cache[prot], cache_res))
        # Cache returns:
        #   None if missing
        #   b'' if blast did not found anything
        #   numpy arr if blast found stuff

    taxids_to_get = set()
    prots_to_get = defaultdict(set)

    for prot, names in prots.items():
        for name in names:
            for tax_id in blast_request[name]:
                cache_data = raw_cache[prot][tax_id]
                if cache_data is None:
                    # Nothing in cache
                    taxids_to_get.add(tax_id)
                    prots_to_get[name_to_prot[name]].add(tax_id)
                elif not cache_data:
                    # blast did not find anything (cache of "empty result")
                    parsed_cache[prot][tax_id] = None
                else:
                    # got a saved numpy array, parse as a df
                    parsed_cache[prot][tax_id] = pd.read_csv(
                        io.BytesIO(cache_data),
                        header=None, names=COLS.keys(), engine="c", dtype=COLS,
                    )
            await asyncio.sleep(0)

    renderer = TreeRenderer(db, tree, prots, name_to_idx, name_to_prot, user_cond, blast_request, enqueue_tree_gen)

    renderer.render(parsed_cache)
    del parsed_cache

    # prot_list = list(prots_to_get)


    taxid_to_ncbi_taxid = await get_ncbi_taxids_from_cache(taxids_to_get)
    taxids_to_get.difference_update(taxid_to_ncbi_taxid.keys())


    async with httpx.AsyncClient(timeout=3*60) as sess:
        # getting cookies
        await retry(sess.get)("https://blast.ncbi.nlm.nih.gov/Blast.cgi", params={
            "PROGRAM": "blastp",
            "PAGE_TYPE": "BlastSearch",
            "LINK_LOC": "blasthome",
        })


        if taxids_to_get:
            # get ncbi tax names from the taxid number
            db.current = 0
            db.total = len(taxids_to_get)
            db.msg = "Getting organisms"

            async with redis.pipeline(transaction=False) as pipe:
                for taxid in taxids_to_get:
                    res = await retry(sess.get)("https://blast.ncbi.nlm.nih.gov/portal/utils/autocomp.fcgi", params={
                        "dict": "blast_nr_prot_sg",
                        "q": f"taxid:{taxid}",
                    })
                    match = SUGGEST_RE.search(res.content)
                    if not match:
                        print(f"no result for taxid {taxid}")
                        db.total -= 1
                        continue
                    db.current += 1
                    org_name = match.group(1).decode()

                    taxid_to_ncbi_taxid[taxid] = org_name

                    pipe.hset("/cache/taxids-for-blast", taxid, org_name)

                await pipe.execute()

        if not (taxid_to_ncbi_taxid and prots_to_get):
            await renderer.flush()
            return

        prots_to_request = list(prots_to_get.keys())
        prots_to_request.sort()

        MIN_PROT_PER_REQ = 1
        MAX_PROT_PER_REQ = 5
        MAX_WORKERS = 3
        PROT_INCR = 0
        prot_per_req = 5
        should_increase = True

        db.current = 0
        db.total = len(prots_to_request)
        db.msg = "Sending blast request(s)"

        running_tasks: dict[asyncio.Task, list] = {}
        exception_task_count = deque(maxlen=5)


        while prots_to_request or running_tasks:
            if prots_to_request and len(running_tasks) < MAX_WORKERS:
                split_el = min(len(prots_to_request), prot_per_req)
                prot_chunk = prots_to_request[:split_el]
                prots_to_request = prots_to_request[split_el:]

                taxids_to_request = set()
                for prot in prot_chunk:
                    taxids_to_request.update(
                        prots_to_get[prot]
                    )
                taxids_to_request.intersection_update(taxid_to_ncbi_taxid)
                organisms_to_request=[
                    taxid_to_ncbi_taxid[taxid]
                    for taxid in taxids_to_request
                ]

                task = asyncio.create_task(blast_request_task(
                    sess,
                    prot_chunk,
                    taxids_to_request,
                    organisms_to_request,
                    prots_to_get,
                ))
                running_tasks[task] = prot_chunk
            else:
                ready, _ = await asyncio.wait(running_tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
                for done_task in ready:
                    done_task: asyncio.Task
                    try:
                        subresult = done_task.result()
                        renderer.render(subresult, render_now=blast_autoreload)
                        done_prots = running_tasks.pop(done_task)
                        db.current += len(done_prots)

                        if should_increase:
                            prot_per_req = min(prot_per_req + PROT_INCR, MAX_PROT_PER_REQ)

                    except RequestTooLargeException:
                        # returns unprocessed prots to the queue
                        prots_to_request.extend(running_tasks.pop(done_task))
                        prot_per_req = max(prot_per_req - PROT_INCR, MIN_PROT_PER_REQ)
                        should_increase = False
                    except Exception as e:
                        prots_to_request.extend(running_tasks.pop(done_task))
                        # detect if we in a loop and got 5 exceptions without making any progress
                        if len(exception_task_count) == exception_task_count.maxlen and exception_task_count[0] == len(prots_to_request):
                            raise RuntimeError("Same group of proteins caused the error 5 times") from e
                        else:
                            exception_task_count.append(len(prots_to_request))
                        print("Sleeping 2 min to avioid potential ban, error encountered:")
                        traceback.print_exc()
                        await asyncio.sleep(2*60)

        await renderer.flush()
