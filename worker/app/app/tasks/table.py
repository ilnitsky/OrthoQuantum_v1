import asyncio
from hashlib import sha256
import urllib.error
import math
import itertools
import re
import csv
from collections import defaultdict
from time import time
from typing import Optional
from io import StringIO
import json


from aioredis.client import Pipeline
import pandas as pd
import anyio
import httpx

from . import table_sync
from ..task_manager import queue_manager, get_db, ReportErrorException
from ..redis import redis, LEVELS, enqueue, update, happend
from ..utils import retry, case_insensitive_unique, json_minify, case_insensitive_top_trunc



TABLE_COLUMNS = [
    "label",
    "Name",
    "description",
    "clade",
    "evolRate",
    "totalGenesCount",
    "multiCopyGenesCount",
    "singleCopyGenesCount",
    "inSpeciesCount",
    # "medianExonsCount", "stddevExonsCount",
    "medianProteinLength",
    "stddevProteinLength"
]

REQUEST_COLUMNS = TABLE_COLUMNS.copy()
try:
    REQUEST_COLUMNS.remove("Name")
except ValueError:
    pass
REQUEST_COLUMNS.append("og")


PROTTREE_PROT_NAME = re.compile(r"[a-zA-Z0-9]+")


async def fetch_orthogroups(orthogroups_to_fetch: list[str], dash_columns: list[str]):
    db = get_db()
    async def progress(items_in_front):
        if items_in_front > 0:
            db.msg = f"In queue to request orthogroup info ({items_in_front} tasks in front)"
        elif items_in_front == 0:
            db.msg = "Requesting orthogroup info"
            await db.sync()

    min_items_per_chunk = 10
    max_items_per_chunk = 50
    preferred_chunk_count = 10

    chunk_count = max(
        min(preferred_chunk_count, math.ceil(len(orthogroups_to_fetch) / min_items_per_chunk)), # target request count
        math.ceil(len(orthogroups_to_fetch) / max_items_per_chunk), # minimal num of requests
    )
    chunk_length = math.ceil(len(orthogroups_to_fetch)/chunk_count)

    tasks = [
        table_sync.ortho_data_get(
            orthogroups_to_fetch[i*chunk_length:(i+1)*chunk_length],
            dash_columns,
        )
        for i in range(chunk_count)
    ]
    tasks[0].set_progress_callback(progress)

    og_info : dict[str, dict[str, str]] = {}


    try:
        for f in asyncio.as_completed(tasks):
            og_info_part = await f
            og_info_part: dict[str, Optional[dict[str, str]]]

            for og, data in og_info_part.items():
                if data:
                    db.current += 1
                    og_info[og] = data
                else:
                    db.total -= 1
    except:
        for t in tasks:
            t.cancel()
        raise

    cur_time = int(time())
    async with redis.pipeline(transaction=False) as pipe:
        for og, og_data in og_info.items():
            pipe.hset(f"/cache/ortho/{og}/data", mapping=og_data)
            pipe.set(f"/cache/ortho/{og}/accessed", cur_time)
            pipe.setnx(f"/cache/ortho/{og}/created", cur_time)
        await pipe.execute()

    return og_info

# https://www.uniprot.org/help/accession_numbers
VALID_UNIPROT_IDS = re.compile(r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}")

# level_orthodb_id = 7742 # Vertebrata|7742

# uniprot through tab file

@retry
async def get_gene_name(sess:httpx.AsyncClient, ortho_id, species):

    resp = await sess.get(
        "https://v101.orthodb.org/tab",
        params={
            "id": ortho_id,
            "species": species,
        },
        headers={
            'Connection': 'keep-alive',
            'sec-ch-ua': '"Chromium";v="95", ";Not A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4619.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
        }
    )

    assert resp.is_success, (resp.status_code, resp.text)
    try:
        reader = csv.reader(StringIO(resp.text), dialect="excel-tab")
        header = next(reader)
        int_prot_id_col_n = header.index('int_prot_id')
        assert int_prot_id_col_n != -1
        pub_gene_id_col_n = header.index('pub_gene_id')
        assert pub_gene_id_col_n != -1
    except Exception:
        # error here probably means that nothing was found or client error
        return '<NA in selected species>', ''
    try:
        prot_ids, gene_names = zip(*((row[int_prot_id_col_n], row[pub_gene_id_col_n]) for row in reader))
        return case_insensitive_top_trunc(gene_names), prot_ids
    except Exception:
        return '<NA in selected species>', ''

@retry
async def search_prot(sess:httpx.AsyncClient, prot_id, level_orthodb_id, gene_name_species):
    resp = await sess.get(
        "https://www.orthodb.org/pgrest/rpc/search",
        params={
            "query": prot_id,
            "level": level_orthodb_id,
            "species": level_orthodb_id,
            "skip": 0,
            "limit": 100,
        },
        headers={
            'authority': 'www.orthodb.org',
            'cache-control': 'max-age=0',
            'sec-ch-ua': '"Chromium";v="95", ";Not A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4619.0 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'sec-fetch-site': 'none',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-user': '?1',
            'sec-fetch-dest': 'document',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'cookie': f'universal=; singlecopy=; cookieconsent_status=dismiss; species={level_orthodb_id}; level=',
        }
    )

    assert resp.is_success, (resp.status_code, resp.text)
    rj = resp.json()

    assert rj['status'] == 'ok'
    if not rj.get('bigdata'):
        return None, None
    if len(rj['bigdata']) == 1:
        record = rj['bigdata'][0]
        if record['id'] != record['public_id']:
            print("Note: dissimilar IDs", level_orthodb_id, prot_id, record)
        gene_name, prot_ids = await get_gene_name(sess, record["id"], gene_name_species)
        return True, [prot_id, record["id"], gene_name, prot_ids]

    rj['bigdata'] = sorted(rj['bigdata'], key=lambda x: x.get('relevance', 0), reverse=True)

    res = []

    for record in rj['bigdata']:
        if record['id'] != record['public_id']:
            print("Note: dissimilar IDs", level_orthodb_id, prot_id, record)
        gene_name, prot_ids = await get_gene_name(sess, record["id"], gene_name_species)

        res.append([
            prot_id, # "PIWIL2"
            record["id"], # "164772at7742"
            gene_name, # "SMPDL3A;SMPDL3B"
            record["name"], # "Acid sphingomyelinase-like phosphodiesterase"
            int(record['gene_count']), # "504"
            int(record['present_in']), # "243"
            prot_ids,
        ])
    return False, res

def split_uniprot_prots(prots):
    uniprot = []
    nonuniprot = []
    for prot in prots:
        if VALID_UNIPROT_IDS.match(prot):
            uniprot.append(prot)
        else:
            nonuniprot.append(prot)
    return uniprot, nonuniprot

@queue_manager.add_handler("/queues/table")
async def table():
    db = get_db()
    db.current = 0
    db.msg = "Getting proteins"

    @db.transaction
    async def res(pipe: Pipeline):
        pipe.multi()
        pipe.hmget(db.state_key, 'input_proteins_parsed', 'taxid_input', 'input_tax_level', 'extra_hash', 'extra_auto_select', 'extra_table_selected_rows')

    prot_ids_text, taxid_input, level_id, extra_hash, auto_selection, extra_table_selected_rows = (await res)[0]
    prot_ids: list[str] = prot_ids_text.split()
    if len(prot_ids) == 0:
        raise ReportErrorException('No data provided!')
    db.total = len(prot_ids)

    _, level_orthodb_id, _ = LEVELS[int(level_id)]


    cur_hash = sha256(f'{level_orthodb_id} {taxid_input} {prot_ids_text}'.encode()).hexdigest()
    regen_table = extra_hash != cur_hash

    if extra_table_selected_rows:
        selected_rows = json.loads(extra_table_selected_rows)
    else:
        selected_rows = []

    selected = defaultdict(set)
    try:
        tbl = pd.read_pickle(db.task_dir/"Extra_table.pkl")
        for k, t in tbl.loc[selected_rows,[0,1]].itertuples(index=False):
            selected[k.strip('*')].add(t)
        if not regen_table:
            assert not tbl.empty
            tbl.loc[:, tbl.columns[-1]] = False
            tbl.loc[selected_rows, tbl.columns[-1]] = True
            tbl[0] = tbl[0].str.strip("*")
    except Exception:
        regen_table = True

    auto_selection = bool(int(auto_selection or 0))

    main_tbl = []
    uniprot_main_tbl = []
    missing_prots = []

    new_selections = []
    old_selections = []

    prots = {}

    async with redis.pipeline(transaction=False) as pipe:
        pipe.hmget(f"/cache/orthoreq/{level_orthodb_id}/{taxid_input}/data", prot_ids)
        pipe.set(f"/cache/orthoreq/{level_orthodb_id}/{taxid_input}/accessed", int(time()), xx=True)

        cache_data = (await pipe.execute())[0]
    for prot_id, s in zip(prot_ids, cache_data):
        if not s:
            continue
        try:
            is_single, res = json.loads(s)
            if is_single:
                res[-1] = set(res[-1])
            else:
                for row in res:
                    row[-1] = set(row[-1])
            prots[prot_id] = (is_single, res)
            db.current += 1
        except Exception:
            __import__("traceback").print_exc()
            pass
    prots_to_get = set(prot_ids)
    prots_to_get.difference_update(prots.keys())


    if prots_to_get:
        async with redis.pipeline(transaction=False) as pipe:
            uniprot, nonuniprot = split_uniprot_prots(prots_to_get)
            if uniprot:
                # old search via uniprot
                res_dict = await table_sync.orthodb_get(level_orthodb_id, uniprot)
                for uniprot_id in uniprot:
                    if len(res_dict.get(uniprot_id, ())) != 1:
                        # failed to get these uniprot proteins the old way, let's try the new way
                        nonuniprot.append(uniprot_id)
                        continue
                    # single
                    label, name = next(iter(res_dict[uniprot_id].items()))
                    res = [prot_id, label, name, prot_id]
                    uniprot_main_tbl.append(res)
                    res[-1] = [res[-1]]
                    db.current += 1
                    pipe.hset(f"/cache/orthoreq/{level_orthodb_id}/{taxid_input}/data", prot_id, json.dumps((True, res), ensure_ascii=False, separators=(',', ':')))
            if nonuniprot:
                async with httpx.AsyncClient() as sess:
                    some_set = False

                    for prot_id in nonuniprot:
                        try:
                            is_single, res = await search_prot(sess, prot_id, level_orthodb_id, taxid_input)
                        except Exception as e:
                            __import__("traceback").print_exc()
                            res = None

                        if res is None:
                            db.total -= 1
                            missing_prots.append(prot_id)
                            continue
                        db.current += 1
                        pipe.hset(f"/cache/orthoreq/{level_orthodb_id}/{taxid_input}/data", prot_id, json.dumps((is_single, res), ensure_ascii=False, separators=(',', ':')))
                        some_set = True
                        if is_single:
                            res[-1] = set(res[-1])
                        else:
                            for row in res:
                                row[-1] = set(row[-1])
                        prots[prot_id] = (is_single, res)

                    if some_set:
                        cur_time = int(time())
                        pipe.set(f"/cache/orthoreq/{level_orthodb_id}/{taxid_input}/accessed", cur_time)
                        pipe.setnx(f"/cache/orthoreq/{level_orthodb_id}/{taxid_input}/created", cur_time)
                        await pipe.execute()

    for prot_id, (is_single, res) in prots.items():
        if is_single:
            # only 1 result, can directly add to the main thingy
            main_tbl.append(res)
            continue

        selected_ortho = selected.get(prot_id, set())
        if not regen_table:
            for row in res:
                if row[1] not in selected_ortho:
                    continue

                main_tbl.append(
                    [prot_id, row[1], row[2], row[-1]]
                )
        else:
            has_selected = False

            for row in res:
                row_selected = row[1] in selected_ortho
                has_selected = has_selected or row_selected
                row.append(row_selected)

            if (not has_selected) and auto_selection:
                res[0][-1] = True
                main_tbl.append(
                    [prot_id, res[0][1], res[0][2], res[0][-2]]
                )
                has_selected = True

            if has_selected:
                old_selections.extend(res)
            else:
                # select most relevant
                res[0][-1] = True
                new_selections.extend(res)


    if missing_prots:
        db["missing_prots"] = ', '.join(missing_prots)
    else:
        db["missing_prots"] = ''


    if regen_table:
        # changed the table itself
        if new_selections:
            tbl = pd.DataFrame.from_records(new_selections)
            tbl[0] = tbl[0].map('**{}**'.format)
            tbl = pd.concat([tbl, pd.DataFrame.from_records(old_selections)], copy=False)
        else:
            tbl = pd.DataFrame.from_records(old_selections)
        tbl[1] = tbl[1].map('[{0}](https://v101.orthodb.org/fasta?id={0})'.format)

        async with db.atomic_file(db.task_dir / "Extra_table.pkl") as tmp_file:
            await table_sync.pickle_df(tmp_file, tbl)
        db['extra_hash'] = cur_hash
        if not tbl.empty:
            db["extra_table"] = db.q_id
            if new_selections:
                return
        else:
            db["extra_table"] = ''
    elif extra_table_selected_rows:
        # changed only selection
        async with db.atomic_file(db.task_dir / "Extra_table.pkl") as tmp_file:
            await table_sync.pickle_df(tmp_file, tbl)
        db["extra_table_selected_rows"]=''
        if not tbl.empty:
            db["extra_table"] = db.q_id
        else:
            db["extra_table"] = ''

    if main_tbl:
        res = await table_sync.orthodb_get_uniprot([r[-1] for r in main_tbl])
        for q, a in zip(main_tbl, res):
            q[-1] = a
    main_tbl.extend(uniprot_main_tbl)

    if not main_tbl:
        raise ReportErrorException('No proteins found')

    db.current = 0
    db.total = None
    db.msg = "Getting orthogroup info"

    async with db.atomic_file(db.task_dir / "OG.csv") as tmp_file:
        uniprot_df = await table_sync.process_prot_data(
            main_tbl,
            tmp_file,
        )

    # Can start visualization right now

    @db.transaction
    async def res(pipe: Pipeline):
        pipe.multi()
        await enqueue(
            task_id=db.task_id,
            stage="vis",
            redis_client=pipe,
        )
        update(
            db.task_id, pipe,
            progress_vis_msg='Building visualization',
        )
    await res

    uniprot_df: pd.DataFrame

    og_list = uniprot_df['label']
    db.total = len(og_list)

    orthogroups_to_fetch = []

    og_info = defaultdict(dict)

    cur_time = int(time())
    async with redis.pipeline(transaction=False) as pipe:
        for og in og_list:
            pipe.hmget(f"/cache/ortho/{og}/data", REQUEST_COLUMNS)
            pipe.set(f"/cache/ortho/{og}/accessed", cur_time, xx=True)

        cache_data = (await pipe.execute())[::2]

    for og, data in zip(og_list, cache_data):
        if None in data:
            continue
        og_info[og] = dict(zip(REQUEST_COLUMNS, data))

    db.current = len(og_info)
    orthogroups_to_fetch = list(set(og_list)-og_info.keys())

    try:
        if orthogroups_to_fetch:
            og_info.update(
                await fetch_orthogroups(
                    orthogroups_to_fetch=orthogroups_to_fetch,
                    dash_columns=REQUEST_COLUMNS,
                )
            )
    except urllib.error.HTTPError as e:
        if e.code == 502:
            await db.report_error("Some data is missing: orthodb.org sparql server is down", cancel_rest=False)
        else:
            raise

    og_info_df = pd.DataFrame(
        (
            vals.values()
            for vals in og_info.values()
        ),
        columns=REQUEST_COLUMNS,
    )

    og_info_df = pd.merge(og_info_df, uniprot_df, on='label', how='right')[TABLE_COLUMNS]

    #prepare datatable update
    def add_link(s:re.Match):
        return f"[{s.group(0)}](/prottree?task_id={db.task_id}&prot_id={s.group(0)})"

    og_info_df['Name'] = og_info_df['Name'].str.replace(PROTTREE_PROT_NAME, add_link)
    og_info_df['label'] = og_info_df['label'].map('[{0}](https://v101.orthodb.org/fasta?id={0})'.format)

    og_info_df.columns = list(range(len(og_info_df.columns)))
    async with db.atomic_file(db.task_dir / "Info_table.pkl") as tmp_file:
        await table_sync.pickle_df(tmp_file, og_info_df)

    db["table"] = db.q_id


