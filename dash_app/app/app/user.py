from pathlib import Path
from urllib.parse import quote
import secrets

import flask

import redis

import time

for attempt in range(10):
    try:
        db = redis.Redis("redis", encoding="utf-8", decode_responses=True)
        db.ping()
        break
    except Exception:
        if attempt == 9:
            raise
        time.sleep(1)


# TODO: change to something more proper
# data will be stored at DATA_PATH / "user_id"

DATA_PATH = Path.cwd() / "user_data"
DATA_PATH.mkdir(exist_ok=True)


def register():
    # TODO: put in DB
    exc = None
    for _ in range(10):
        try:
            flask.session["USER_ID"] = secrets.token_hex(16)
            path().mkdir()
            break
        except Exception as e:
            exc = e
    else:
        raise RuntimeError("Failed to create a user dir") from exc


def is_logged_in() -> bool:
    try:
        if not path().exists():
            del flask.session["USER_ID"]
            return False
        return True
    except Exception:
        return False


def path() -> Path:
    """Returns the path appropriate to store user's files"""
    try:
        return DATA_PATH / flask.session["USER_ID"]
    except Exception:
        raise RuntimeError("XXX user not logged in!")


def url_for(filename):
    return f'/files/{flask.session["USER_ID"]}/{quote(filename)}'


from typing import Any, Optional


_get_length_script = db.register_script("""
    -- KEYS[1] - queue_key

    -- ARGV[1] - worker_group_name  //worker_group
    -- ARGV[2] - current (used as element id source) "1622079118529-0"

    -- returns: >0 if there are items in front of the current
    -- 0 if already working
    -- -1 on error

    local info = redis.call('XINFO', 'GROUPS', KEYS[1])
    local last_id = '-'
    local found_name = false
    for i = 1, #info do
        last_id = '-'
        found_name = false
        for j = 1, #info[i], 2 do
            if (info[i][j] == 'name') then
                if (info[i][j+1] == ARGV[1]) then
                    found_name = true
                    if (last_id ~= '-') then
                        break
                    end
                else
                    break
                end
            elseif (info[i][j] == 'last-delivered-id') then
                last_id = info[i][j+1]
                if (found_name) then
                    break
                end
            end
        end
        if (found_name) then
            break
        end
    end
    if (not found_name) then
        return -1
    end

    local res = #redis.call('XRANGE', KEYS[1], last_id, ARGV[2])
    if (res == 0) then
        return 0
    else
        return res - 1
    end

""")


def get_queue_length(queue_key, worker_group_name, current, redis_client=None):
    return _get_length_script(
        keys=(queue_key,),
        args=(worker_group_name, current),
        client=redis_client,
    )



_enqueue_script = db.register_script("""
    -- KEYS[1] - version
    -- KEYS[2] - queue
    -- KEYS[3] - queue_id_dest (empty string to skip)
    local version = redis.call('incr', KEYS[1])
    local queue_id = redis.call('xadd', KEYS[2], '*', 'version', version, unpack(ARGV))
    if (KEYS[3] ~= '') then
        redis.call('set', KEYS[3], queue_id)
    end
    return {version, queue_id}
""")
from itertools import chain
def enqueue(version_key, queue_key, queue_id_dest=None, params: Optional[dict[str, Any]]=None, redis_client=None, **kwargs):
    if params:
        kwargs.update(params)
    return _enqueue_script(
        keys=(
            version_key,
            queue_key,
            queue_id_dest or '',
        ),
        args=list(chain.from_iterable(kwargs.items())),
        client=redis_client,
    )
