"""Bound saved query history without deleting files used by active workers."""
import re
import shutil

SAVED_QUERIES = 15
VISIBLE_QUERIES = 10


def prune_history(db, user_id, data_path):
    history = f'/users/{user_id}/tasks'
    retired = f'/users/{user_id}/retired_tasks'
    # Atomically move overflow to a cleanup set so concurrent requests cannot
    # lose tasks awaiting cleanup.
    db.eval('''
        local old = redis.call('LRANGE', KEYS[1], 0, -16)
        for _, id in ipairs(old) do redis.call('SADD', KEYS[2], id) end
        redis.call('LTRIM', KEYS[1], -15, -1)
        return #old
    ''', 2, history, retired)
    for task_id in db.smembers(retired):
        if not re.fullmatch(r'[0-9a-f]{32}', task_id):
            continue
        prefix = f'/tasks/{task_id}'
        if db.get(f'{prefix}/user_id') != user_id:
            db.srem(retired, task_id)
            continue
        if db.hlen(f'{prefix}/running') or db.hlen(f'{prefix}/enqueued'):
            continue
        shutil.rmtree(data_path / task_id, ignore_errors=True)
        keys = list(db.scan_iter(match=f'{prefix}/*'))
        if keys:
            db.unlink(*keys)
        db.srem(retired, task_id)
