import asyncio
from dataclasses import dataclass
from collections.abc import Callable, Coroutine
from typing import Any, Optional
from functools import wraps

from aioredis import WatchError
from aioredis.client import Pipeline

from .exceptions import VersionChangedException
from ..redis import redis, GROUP
from ..utils import decode_int, DATA_PATH

@dataclass
class ProgressUpdate:
    _current : Optional[int] = None
    _current_delta : int = 0
    _total : Optional[int] = None
    _total_delta : int = 0
    other = {}

    def reset(self):
        res = dict()
        default_vals = {
            'current': None,
            'current_delta': 0,
            'total': None,
            'total_delta': 0,
        }
        for k, default_val in default_vals.items():
            val = getattr(self, k)
            if val != default_val:
                res[k] = val
                setattr(self, f'_{k}', default_val)
        res.update(self.other)
        self.other.clear()
        return res

    @property
    def current_delta(self):
        return self._current_delta

    @current_delta.setter
    def current_delta(self, val: int):
        if val is None:
            return
        if self._current is not None:
            self._current += val
        else:
            self._current_delta += val

    @property
    def total_delta(self):
        return self._total_delta

    @total_delta.setter
    def total_delta(self, val: int):
        if val is None:
            return
        if self._total is not None:
            self._total += val
        else:
            self._total_delta += val

    @property
    def total(self):
        return self._total

    @total.setter
    def total(self, val:int):
        if val is not None:
            self._total = val
            self._total_delta = 0

    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, val:int):
        if val is not None:
            self._current = val
            self._current_delta = 0

class DbClient():
    FLUSH_DELAY = 0.3

    def __init__(self, task_id: str, stage: str, version: int, version_key: str = None):
        self.task_id: str = task_id
        self.stage: str = stage
        self.version: int = version
        self.task_dir = DATA_PATH / task_id
        self._progress_task: Optional[asyncio.Task] = None
        self._report_flush: Optional[asyncio.Future] = None
        self._report_send_lock = asyncio.Lock()
        self._progress = ProgressUpdate()
        if version_key is None:
            self.task_dir.mkdir(exist_ok=True)
            version_key = f"/tasks/{self.task_id}/stage/{self.stage}/version"
        self._verison_key = version_key

    def substage(self, stage_name):
        return DbClient(
            task_id=self.task_id,
            stage=stage_name,
            version=self.version,
            version_key=self._verison_key,
        )

    def transaction(self, func: Callable[[Pipeline], Coroutine[Any, Any, None]]) -> Coroutine[Any, Any, list]:
        @wraps(func)
        async def wrapper():
            async with redis.pipeline(transaction=True) as pipe:
                while True:
                    try:
                        await pipe.watch(self._verison_key)
                        db_version = decode_int(await pipe.get(self._verison_key))
                        if self.version != db_version:
                            raise VersionChangedException()
                        await func(pipe)
                        return await pipe.execute()
                    except WatchError:
                        continue
        return wrapper()

    async def _report_progress(self):
        try:
            await asyncio.wait_for(asyncio.shield(self._report_flush), timeout=self.FLUSH_DELAY)
        except asyncio.CancelledError:
            if self._report_flush.cancelled():
                self._report_flush = None
            if asyncio.current_task().cancelled():
                raise
        except asyncio.TimeoutError:
            pass

        async with self._report_send_lock:
            self._progress_task = None
            res = self._progress.reset()
            if res:
                @self.transaction
                async def send_report(pipe: Pipeline):
                    pipe.multi()

                    self._set_progress(
                        pipe=pipe,
                        **res,
                    )
                await send_report

    def _set_progress(self, pipe:Pipeline, current:int=None, total:int=None, current_delta:int=None, total_delta:int=None, **other):
        key = f"/tasks/{self.task_id}/progress/{self.stage}"
        if current is not None:
            other["current"] = current
        elif current_delta:
            pipe.hincrby(key, "current", current_delta)

        if total is not None:
            other["total"] = total
        elif total_delta:
            pipe.hincrby(key, "total", total_delta)

        if other:
            pipe.hset(key, mapping=other)


    def report_progress(self, current:int=None, total:int=None, current_delta:int=None, total_delta:int=None, pipe:Pipeline=None, **other):
        self._progress.current = current
        self._progress.current_delta = current_delta
        self._progress.total = total
        self._progress.total_delta = total_delta
        self._progress.other.update(other)
        if pipe:
            if res := self._progress.reset():
                self._set_progress(
                    pipe=pipe,
                    **res
                )
        else:
            if (self._progress_task is None or self._progress_task.done()):
                self._progress_task = asyncio.create_task(self._report_progress())
                if not self._report_flush:
                    self._report_flush = asyncio.Future()

    async def flush_progress(self, current:int=None, total:int=None, current_delta:int=None, total_delta:int=None, **other):
        self.report_progress(current=current, total=total, current_delta=current_delta, total_delta=total_delta, **other)
        self._report_flush.cancel()
        await self._progress_task

    async def report_error(self, message, cancel_rest=True):
        @self.transaction
        async def tx(pipe: Pipeline):
            out_msg = message
            key = f"/tasks/{self.task_id}/progress/{self.stage}"
            await pipe.watch(key)
            status = await pipe.hget(key, "status")
            if status == "Error":
                old_message = await pipe.hget(key, "message")
                out_msg = f'{old_message}; {out_msg}'
            pipe.multi()
            pipe.hmset(key, {
                "message": out_msg,
                "status": "Error",
                "total": -2,
            })
            if cancel_rest:
                pipe.incr(f"/tasks/{self.task_id}/stage/{self.stage}/version")
        await tx
