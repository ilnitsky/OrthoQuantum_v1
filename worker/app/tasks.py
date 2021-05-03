import contextlib
from functools import partialmethod
import itertools
import time
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import redis
import celery
from celery.exceptions import Ignore, Reject, CeleryError

import pandas as pd
from redis.client import Pipeline

from protein_fetcher import orthodb_get, uniprot_get, ortho_data_get
from db import db, queueinfo_upd

app = celery.Celery('worker', broker='redis://redis/1', backend='redis://redis/1')

DATA_PATH = Path.cwd() / "user_data"
if not DATA_PATH.exists():
    raise RuntimeError("No data dir!")

INVALID_PROT_IDS = re.compile(r"[^A-Za-z0-9\-\n \t]+")


#region utils
def fake_delay():
    # time.sleep(random.randint(5000, 10000)/1000)
    pass


def chunker(items:list, min_chunk_len, max_chunks):
    chunk_count = min(
        1 + len(items) // min_chunk_len,
        max_chunks,
    )
    items_per_chunk = math.ceil(len(items)/chunk_count)

    it = iter(items)
    while True:
        res = tuple(itertools.islice(it, items_per_chunk))
        if not res:
            break
        yield res
#endregion


#region dbm
class RollbackException(Exception):
    pass

class ReportErrorException(Exception):
    def __init__(self, message=None):
        super().__init__()
        self.message = message

class DBManager():
    def __init__(self, stage, task_id, version, progress_interval=1):
        self.stage = stage
        self.task_id = task_id
        self.version = version

        self._curr_incr = 0
        self._total_incr = 0
        self._can_use_relative_progress = 0
        self.last_progress = 0
        self.progress_interval = progress_interval

    def report_error(self, message, cancel_rest=True):
        @self.tx
        def res(pipe:Pipeline):
            pipe.watch(f"/tasks/{self.task_id}/stage/{self.stage}/status")
            status = pipe.get(f"/tasks/{self.task_id}/stage/{self.stage}/status")
            pipe.multi()
            if status == "Error":
                pipe.append(f"/tasks/{self.task_id}/stage/{self.stage}/message", f'; {message}')
            else:
                pipe.mset({
                    f"/tasks/{self.task_id}/stage/{self.stage}/message": message,
                    f"/tasks/{self.task_id}/stage/{self.stage}/status": "Error",
                    f"/tasks/{self.task_id}/stage/{self.stage}/total": -2,
                })
            if cancel_rest:
                pipe.incr(f"/tasks/{self.task_id}/stage/{self.stage}/version")


    def run_code(self, func, *args, cancel_on_error=True, **kwargs):
        """Runs func with error reporting on exceptions"""
        try:
            return func(*args, **kwargs)
        except CeleryError:
            raise
        except ReportErrorException as e:
            self.report_error(e.message, cancel_rest=cancel_on_error)
            if e.__cause__ is not None:
                e = e.__cause__
            raise Reject(e, requeue=False)
        except Exception as e:
            self.report_error("Internal server error", cancel_rest=cancel_on_error)
            raise Reject(e, requeue=False)



    def tx(self, func=None, allow_read_only=False, retry_delay=0) -> list:
        """Decorator immediately runs the function in transaction mode
        function must not call pipe.execute() or pipe.discard():
            return normally to get pipe.execute()'s results assigned to the function name
            raise any Exception to call pipe.discard and reraise that execption
            raise RollbackException to call pipe.discard and exit with result "None"

        function may be rerun multiple times in case watch error is triggered, be careful with side-effects

        function must accept 1 argument: pipeline in immediate execution state
        if allow_read_only=True function must accept a second parameter: can_write (bool)
            in case can_write is false function must not perform any write operations on the object task_id
        """
        if func is None:
            return partialmethod(self.run_tx, allow_read_only=allow_read_only, retry_delay=retry_delay)

        with db.pipeline(transaction=True) as pipe:
            while True:
                try:
                    pipe.watch(f"/tasks/{self.task_id}/stage/{self.stage}/version")
                    version = int(pipe.get(f"/tasks/{self.task_id}/stage/{self.stage}/version"))
                    can_write = version == self.version
                    if allow_read_only:
                        args = (pipe, can_write)
                    else:
                        if not can_write:
                            raise Ignore()
                        args = (pipe,)
                    try:
                        func(*args)
                    except RollbackException:
                        with contextlib.suppress(Exception):
                            pipe.discard()
                        res = None
                    except Exception:
                        with contextlib.suppress(Exception):
                            pipe.discard()
                        raise
                    else:
                        res = pipe.execute()
                    return res
                except redis.WatchError:
                    if retry_delay:
                        time.sleep(retry_delay)
                    continue

    def __enter__(self):
        self._can_use_relative_progress += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._can_use_relative_progress == 1:
            if self._curr_incr or self._total_incr:
                self.progress(flush=True)
        self._can_use_relative_progress -= 1

    def set_progress(self, current=None, total=None, message=None, pipe: Pipeline = None):
        l = locals()
        upd = {
            f"/tasks/{self.task_id}/stage/{self.stage}/{k}": l[k]
            for k in ('current', 'total', 'message')
            if l[k] is not None
        }
        if upd:
            if pipe is None:
                @self.tx
                def res(pipe: redis.client.Pipeline):
                    pipe.multi()
                    pipe.mset(upd)
            else:
                pipe.mset(upd)

        self._curr_incr = 0
        self._total_incr = 0
        return True

    def progress(self, incr_curr=0, incr_total=0, message=None, flush=False):
        if self._can_use_relative_progress == 0:
            # Can't trust that the progress would be flushed later, so force-flushing now
            flush = True
        self._curr_incr += incr_curr
        self._total_incr += incr_total
        if not (message or flush):
            # apply time limits
            if time.time() - self.last_progress < self.progress_interval:
                return False

        if self._curr_incr or self._total_incr or message is not None:
            @self.tx
            def res(pipe: redis.client.Pipeline):
                pipe.multi()
                if message is not None:
                    pipe.set(f"/tasks/{self.task_id}/stage/{self.stage}/message", message)
                if self._curr_incr != 0:
                    pipe.incrby(f"/tasks/{self.task_id}/stage/{self.stage}/current", self._curr_incr)
                if self._total_incr != 0:
                    pipe.incrby(f"/tasks/{self.task_id}/stage/{self.stage}/total", self._total_incr)
            self._curr_incr = 0
            self._total_incr = 0

        self.last_progress = time.time()
        return True
#endregion

def decode_str(item:bytes, default='') -> str:
    if item:
        return item.decode()
    else:
        return default

def decode_int(item:bytes, default=0) -> int:
    if item:
        return int(item)
    else:
        return default




@app.task()
def build_table(task_id, version):
    dbm = DBManager("table", task_id, version)
    dbm.run_code(do_build_table, dbm, task_id, version)

def do_build_table(dbm: DBManager, task_id, version):
    prot_ids = None
    fake_delay()
    @dbm.tx
    def res(pipe: Pipeline):
        nonlocal prot_ids
        queueinfo_upd(task_id, client=pipe)
        prot_req = pipe.get(f"/tasks/{task_id}/request/proteins")

        prot_ids = list(dict.fromkeys( # removing duplicates
            INVALID_PROT_IDS.sub("", decode_str(prot_req)).upper().split(),
        ))

        pipe.multi()
        pipe.set(f"/tasks/{task_id}/stage/table/status", "Executing")
        dbm.set_progress(
            current=0,
            total=len(prot_ids),
            message="Getting proteins",
            pipe=pipe,
        )
        pipe.get(f"/tasks/{task_id}/request/dropdown1")
    fake_delay()
    level = decode_str(res[-1]).split('-')[0]
    prot_ids : list


    # Filter out already cached proteins
    cur_time = int(time.time())
    with db.pipeline(transaction=False) as pipe:
        for prot_id in prot_ids:
            pipe.set(f"/cache/uniprot/{level}/{prot_id}/accessed", cur_time, xx=True)

        # If the protein doesn't exist - the set command returns None.
        # We get those proteins and return their IDs so they could be fetched
        prots_to_fetch = [
            prot_ids[i]
            for i, was_set in enumerate(pipe.execute())
            if not was_set
        ]
    dbm.set_progress(current=len(prot_ids) - len(prots_to_fetch))
    fake_delay()

    group = celery.group(
        _fetch_proteins.s(
            task_id,
            version,
            prot_chunk,
            level,
        )
        for prot_chunk in chunker(prots_to_fetch, min_chunk_len=2, max_chunks=5)
    )

    pipeline = (
        group |
        _get_orthogroups.si(
            task_id,
            version,
            prot_ids,
            level,
        )
    )
    pipeline.apply_async()


@app.task()
def _fetch_proteins(task_id, version, prot_ids, level):
    dbm = DBManager("table", task_id, version)
    dbm.run_code(do_fetch_proteins, dbm, task_id, prot_ids, level, cancel_on_error=False)

def do_fetch_proteins(dbm:DBManager, task_id, prot_ids, level):
    """Task fetches protein info and puts it into the cache"""
    fake_delay()
    prots = defaultdict(list)
    req_ids = set(prot_ids)
    prots.update(orthodb_get(level, req_ids))
    fake_delay()

    dbm.progress(incr_curr=len(prots))
    sparql_misses = req_ids - prots.keys()

    missing_prots = []

    def write_missing(pipe: Pipeline):
        pipe.multi()
        pipe.append(f"/tasks/{task_id}/stage/table/missing_msg", f"{', '.join(missing_prots)}, ")

    with dbm:
        for prot_id in sparql_misses:
            res = uniprot_get(prot_id)
            fake_delay()
            if res is None:
                missing_prots.append(prot_id)
                incr_curr = 0
                incr_total = -1
            else:
                incr_curr = 1
                incr_total = 0

            if dbm.progress(incr_curr, incr_total) and missing_prots:
                dbm.tx(write_missing)
                missing_prots.clear()

    if missing_prots:
        dbm.tx(write_missing)
        missing_prots.clear()

    cur_time = int(time.time())
    with db.pipeline(transaction=False) as pipe:
        # Add all prots to the cache
        for prot_id in prots:
            pipe.mset(
                {
                    f"/cache/uniprot/{level}/{prot_id}/data": json.dumps(prots[prot_id], separators=(',', ':')),
                    f"/cache/uniprot/{level}/{prot_id}/accessed": cur_time,
                }
            )
            pipe.setnx(f"/cache/uniprot/{level}/{prot_id}/created", cur_time)
        pipe.execute()

@app.task()
def _get_orthogroups(task_id, version, prot_ids, level):
    dbm = DBManager("table", task_id, version)
    dbm.run_code(do_get_orthogroups, dbm, task_id, prot_ids, level)

def do_get_orthogroups(dbm, task_id, prot_ids, level):
    dbm.set_progress(current=0, total=-1, message="Getting orthogroup info")

    data = list(itertools.chain.from_iterable(
        json.loads(raw_text)
        for raw_text in filter(None, db.mget([
            f"/cache/uniprot/{level}/{prot_id}/data"
            for prot_id in prot_ids
        ]))
    ))
    fake_delay()

    uniprot_df = pd.DataFrame(
        columns=['label', 'Name', 'PID'],
        data=data,
    )

    uniprot_df.replace("", float('nan'), inplace=True)
    uniprot_df.dropna(axis="index", how="any", inplace=True)
    uniprot_df['is_duplicate'] = uniprot_df.duplicated(subset='label')

    og_list = []
    names = []
    uniprot_ACs = []

    # TODO: DataFrame.groupby would be better, but need an example to test
    for row in uniprot_df[uniprot_df.is_duplicate == False].itertuples():
        dup_row_names = uniprot_df[uniprot_df.label == row.label].Name.unique()
        og_list.append(row.label)
        names.append("-".join(dup_row_names))
        uniprot_ACs.append(row.PID)

    dbm.set_progress(total=len(og_list))

    #SPARQL Look For Presence of OGS in Species
    uniprot_df = pd.DataFrame(columns=['label', 'Name', 'UniProt_AC'], data=zip(og_list, names, uniprot_ACs))
    fake_delay()
    task_dir = DATA_PATH / task_id
    task_dir.mkdir(exist_ok=True)

    uniprot_df.to_csv(task_dir/'OG.csv', sep=';', index=False)

    dash_columns = [
        "label",
        "description",
        "clade",
        "evolRate",
        "totalGenesCount",
        "multiCopyGenesCount",
        "singleCopyGenesCount",
        "inSpeciesCount",
        # "medianExonsCount", "stddevExonsCount",
        "medianProteinLength",
        "stddevProteinLength",
        "og"
    ]

    cache_misses = []

    og_info = defaultdict(dict)

    cur_time = int(time.time())
    with db.pipeline(transaction=False) as pipe:
        for og in og_list:
            pipe.hmget(f"/cache/ortho/{og}/data", dash_columns)
            pipe.set(f"/cache/ortho/{og}/accessed", cur_time, xx=True)
        cache_data = pipe.execute()[::2]

    with dbm:
        for og, data in zip(og_list, cache_data):
            for col_name, val in zip(dash_columns, data):
                if val is None:
                    cache_misses.append(og)
                    break
                og_info[og][col_name] = val.decode()
            else:
                # extracted from cache
                fake_delay()
                dbm.progress(incr_curr=1)

    if cache_misses:
        dbm.set_progress(message="Requesting orthogroup info")
        og_info = ortho_data_get(cache_misses, dash_columns)

    cur_time = int(time.time())

    with dbm, db.pipeline(transaction=False) as pipe:
        for og in cache_misses:
            info = og_info[og]
            fake_delay()
            if info:
                dbm.progress(incr_curr=1)
            else:
                dbm.progress(incr_total=-1)
            pipe.hmset(f"/cache/ortho/{og}/data", info)
            pipe.set(f"/cache/ortho/{og}/accessed", cur_time)
            pipe.setnx(f"/cache/ortho/{og}/created", cur_time)
        pipe.execute()

    og_info_df = pd.DataFrame(
        (
            vals.values()
            for vals in og_info.values()
        ),
        columns=dash_columns,
    )
    og_info_df = pd.merge(og_info_df, uniprot_df, on='label')

    display_columns = [
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
    og_info_df = og_info_df[display_columns]

    #prepare datatable update
    table_data = {
        "data": og_info_df.to_dict('records'),
        "columns": [
            {
                "name": i,
                "id": i,
            }
            for i in og_info_df.columns
        ]
    }
    table = json.dumps(table_data, ensure_ascii=False, separators=(',', ':'))

    @dbm.tx
    def res(pipe: Pipeline):
        pipe.multi()
        pipe.mset({
            f"/tasks/{task_id}/stage/table/status": "Done",
            f"/tasks/{task_id}/stage/table/dash-table": table,
        })
