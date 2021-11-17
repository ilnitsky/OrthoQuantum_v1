from pathlib import Path
from itertools import chain
from typing import Any, Optional, Union

import secrets

import flask

import redis

import time

GROUP = "worker_group"

for attempt in range(30):
    try:
        db = redis.Redis("redis", encoding="utf-8", decode_responses=True)
        db.ping()
        db.brpoplpush("/worker_initialied", "/worker_initialied", timeout=0)
        scripts = db.hgetall("/scripts")
        break
    except Exception:
        if attempt == 9:
            raise
        time.sleep(1)


DATA_PATH = Path.cwd() / "user_data"
DATA_PATH.mkdir(exist_ok=True)


def register():
    exc = None
    for _ in range(10):
        try:
            user_id = secrets.token_hex(16)
            if not db.setnx(f"/users/{user_id}/task_counter", "0"):
                continue
            flask.session["USER_ID"] = user_id
            break
        except Exception as e:
            exc = e
    else:
        raise RuntimeError("Failed to create a user") from exc


def is_logged_in() -> bool:
    try:
        if not db.exists(f"/users/{flask.session['USER_ID']}/task_counter"):
            del flask.session["USER_ID"]
            return False
        return True
    except Exception:
        return False

assert 'get_updates' in scripts, 'get_updates is missing!'
assert 'get_updates_new_connection' in scripts, 'get_updates_new_connection is missing!'
def get_updates(task_id:str, last_version:int = None, connection_id:int = None, redis_client=None):
    """
    returns tuple:
        new version
        dict of updated keys and values
    """
    if last_version is None or connection_id is None:
        args = [
            scripts['get_updates_new_connection'],
            4,
            f'/tasks/{task_id}/state/cur_version',
            f'/tasks/{task_id}/state/key_versions',
            f'/tasks/{task_id}/state',
            f"/tasks/{task_id}/connection_counter"
        ]
    else:
        args = [
            scripts['get_updates'],
            5,
            f'/tasks/{task_id}/state/cur_version',
            f'/tasks/{task_id}/state/key_versions',
            f'/tasks/{task_id}/state/key_versions_on_connection_{connection_id}',
            '/scratch/zset',
            f'/tasks/{task_id}/state',

            last_version + 1
        ]

    if redis_client is None:
        return decode_updates_resp(db.evalsha(*args))
    else:
        return redis_client.evalsha(*args)


def decode_updates_resp(upd):
    if len(upd) == 3:
        return int(upd[0]), dict(zip(upd[1], upd[2]))
    else:
        return int(upd[0]), int(upd[1]), dict(zip(upd[2], upd[3]))

assert 'send_updates' in scripts, 'send_updates is missing!'
def _report_updates(task_id:str, *updated_keys, connection_id:int=None, redis_client=None):
    if redis_client is None:
        redis_client = db
    if connection_id is None:
        return redis_client.evalsha(
            scripts['send_updates'],
            2,
            f'/tasks/{task_id}/state/cur_version',
            f'/tasks/{task_id}/state/key_versions',

            *updated_keys
        )
    else:
        return redis_client.evalsha(
            scripts['send_updates'],
            3,
            f'/tasks/{task_id}/state/cur_version',
            f'/tasks/{task_id}/state/key_versions',
            f'/tasks/{task_id}/state/key_versions_on_connection_{connection_id}',

            *updated_keys
        )



def update(task_id:str, connection_id:int=None, redis_pipe=None, update: dict=None, **updates):
    """
    performs hset and report_updates
    if connection_id is provided the update would not be sent to this connection
    """
    if update:
        updates.update(update)
    if not updates:
        raise ValueError("No update data")
    if redis_pipe is None:
        with db.pipeline(transaction=True) as pipe:
            pipe.hset(f'/tasks/{task_id}/state', mapping=updates)
            _report_updates(task_id, *updates.keys(), connection_id=connection_id, redis_client=pipe)
            return pipe.execute()[-1]
    else:
        redis_pipe.hset(f'/tasks/{task_id}/state', mapping=updates)
        return _report_updates(task_id, *updates.keys(), connection_id=connection_id, redis_client=redis_pipe)




assert 'get_queue_pos' in scripts, 'get_queue_pos is missing!'
def get_queue_pos(queue_key, task_q_id, redis_client=None):
    if redis_client is None:
        redis_client = db
    return redis_client.evalsha(
        scripts['get_queue_pos'],
        1, queue_key,
        GROUP, task_q_id,
    )

assert 'enqueue' in scripts, 'enqueue is missing!'
def enqueue(task_id:str, stage:str, params: Optional[dict[str, Any]]=None, redis_client=None, **kwargs):
    if params:
        kwargs.update(params)
    kwargs.setdefault('task_id', task_id)
    kwargs.setdefault('stage', stage)
    if not kwargs:
        raise RuntimeError("empty queue data")

    return _enqueue(
        task_id=task_id,
        stage=stage,
        params=kwargs,
        redis_client=redis_client
    )

def cancel(task_id:str, stage:str, redis_client=None):
    return _enqueue(
        task_id=task_id,
        stage=stage,
        params={},
        redis_client=redis_client
    )

def _enqueue(task_id:str, stage:str, params: dict[str, Any], redis_client=None):
    if redis_client is None:
        redis_client = redis

    args = list(chain.from_iterable(params.items()))
    args.append(GROUP)
    args.append(stage)

    return redis_client.evalsha(
        scripts['enqueue'],
        4,
        f"/queues/{stage}",
        f"/tasks/{task_id}/enqueued",
        f"/tasks/{task_id}/running",
        "/canceled_jobs",

        *args,
    )