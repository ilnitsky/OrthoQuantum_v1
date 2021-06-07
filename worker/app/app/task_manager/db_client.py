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
    _message : Optional[str] = None

    def reset(self):
        self._current = None
        self._current_delta = 0
        self._total = None
        self._total_delta = 0
        self._message = None

    def __bool__(self):
        return any((
            self._current is not None,
            self._current_delta,
            self._total is not None,
            self._total_delta,
            self._message is not None,
        ))

    @property
    def current_delta(self):
        return self._current_delta

    @current_delta.setter
    def current_delta(self, val: int):
        if self._current is not None:
            self._current += val
        else:
            self._current_delta = val

    @property
    def total_delta(self):
        return self._total_delta

    @total_delta.setter
    def total_delta(self, val: int):
        if self._total is not None:
            self._total += val
        else:
            self._total_delta = val

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

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, val:str):
        if val is not None:
            self._message = val

class DbClient():
    FLUSH_DELAY = 0.3

    def __init__(self, task_id: str, stage: str, version: int):
        self.task_id: str = task_id
        self.stage: str = stage
        self.version: int = version
        self.task_dir = DATA_PATH / task_id
        self.task_dir.mkdir(exist_ok=True)
        self._progress_task: Optional[asyncio.Task] = None
        self._report_flush: Optional[asyncio.Future] = None
        self._report_send_lock = asyncio.Lock()
        self._progress = ProgressUpdate()
        self._verison_key = f"/tasks/{self.task_id}/stage/{self.stage}/version"

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
            if not self._progress:
                # no changes at all
                return

            total = self._progress.total
            current = self._progress.current
            message = self._progress.message
            current_delta = self._progress.current_delta
            total_delta = self._progress.total_delta

            self._progress.reset()

            @self.transaction
            async def send_report(pipe: Pipeline):
                pipe.multi()
                self._set_progress(
                    pipe=pipe,
                    current=current,
                    total=total,
                    current_delta=current_delta,
                    total_delta=total_delta,
                    message=message,
                )
            await send_report

    def _set_progress(self, pipe:Pipeline, current:int=None, total:int=None, current_delta:int=None, total_delta:int=None, message:str=None):
        if current is not None:
            pipe.set(f"/tasks/{self.task_id}/stage/{self.stage}/current", current)
        elif current_delta:
            pipe.incrby(f"/tasks/{self.task_id}/stage/{self.stage}/current", current_delta)
        if total is not None:
            pipe.set(f"/tasks/{self.task_id}/stage/{self.stage}/total", total)
        elif total_delta:
            pipe.incrby(f"/tasks/{self.task_id}/stage/{self.stage}/total", total_delta)
        if message is not None:
            pipe.set(f"/tasks/{self.task_id}/stage/{self.stage}/message", message)


    def report_progress(self, current:int=None, total:int=None, current_delta:int=None, total_delta:int=None, message:str=None, pipe:Pipeline=None):
        if pipe:
            self._set_progress(
                pipe=pipe,
                current=current,
                total=total,
                current_delta=current_delta,
                total_delta=total_delta,
                message=message,
            )
            return
        if current is not None:
            self._progress.current = current
        if current_delta is not None:
            self._progress.current_delta += current_delta
        if total is not None:
            self._progress.total = total
        if total_delta is not None:
            self._progress.total_delta += total_delta
        if message is not None:
            self._progress.message = message

        if (self._progress_task is None or self._progress_task.done()):
            self._progress_task = asyncio.create_task(self._report_progress())
            if not self._report_flush:
                self._report_flush = asyncio.Future()

    async def flush_progress(self, current:int=None, total:int=None, current_delta:int=None, total_delta:int=None, message:str=None):
        self.report_progress(current, total, current_delta, total_delta, message)
        self._report_flush.cancel()
        await self._progress_task

    async def report_error(self, message):
        @self.transaction
        async def tx(pipe: Pipeline):
            await pipe.watch(f"/tasks/{self.task_id}/stage/{self.stage}/status")
            status = await pipe.get(f"/tasks/{self.task_id}/stage/{self.stage}/status")
            pipe.multi()
            if status == "Error":
               pipe.append(f"/tasks/{self.task_id}/stage/{self.stage}/message", f'; {message}')
            else:
                pipe.mset({
                    f"/tasks/{self.task_id}/stage/{self.stage}/message": message,
                    f"/tasks/{self.task_id}/stage/{self.stage}/status": "Error",
                    f"/tasks/{self.task_id}/stage/{self.stage}/total": -2,
                })
                pipe.incr(f"/tasks/{self.task_id}/stage/{self.stage}/version")
        await tx
