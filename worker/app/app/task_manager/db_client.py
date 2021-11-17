import asyncio
from collections.abc import Callable, Coroutine
import contextlib
from typing import Any, Awaitable
import contextvars
import anyio
from aioredis import WatchError
from aioredis.client import Pipeline


from .exceptions import ReportErrorException, VersionChangedException, HandledReportErrorException
from ..redis import redis, cancel, report_updates, happend
from ..utils import DATA_PATH, DEBUG


_db_var = contextvars.ContextVar("db")

@contextlib.asynccontextmanager
async def _create_db_client(task_id, stage, q_id, stage_for_progress=None):
    db = DbClient(
        task_id=task_id,
        stage=stage,
        q_id=q_id,
        stage_for_progress=stage_for_progress,
    )
    token = _db_var.set(db)
    try:
        yield db
    except (VersionChangedException, KeyboardInterrupt):
        raise
    except ReportErrorException as e:
        with anyio.CancelScope(shield=True):
            await db.report_error(e.args[0])
        raise HandledReportErrorException() from e
    except Exception as e:
        if DEBUG:
            msg = f"Internal server error: {repr(e)}"
        else:
            msg = "Internal server error"
        with anyio.CancelScope(shield=True):
            await db.report_error(msg)
        raise
    finally:
        _db_var.reset(token)
        with anyio.CancelScope():
            if not (db.is_error is True):
                print("pb_hide", db.stage_for_progress)
                db.pb_hide()
                print("pb_hide", db.stage_for_progress, db._enqueued_update)
            try:
                print("pb_hide db.sync", db.stage_for_progress)
                try:
                    await db.sync()
                except BaseException:
                    if db.stage_for_progress == "vis":
                        __import__("traceback").print_exc()
                    raise
                print("pb_hide db.sync done", db.stage_for_progress)

            finally:
                db._flush_task.cancel()



class PBProps():
    def __init__(self, db_key):
        self._db_key = db_key
        self._name = None
        if self._db_key == 'style':
            self._style_translate_table = {
                True: "error",
                False: "progress",
                None: None,
            }
        else:
            self._style_translate_table = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance: "DbClient", owner=None):
        return instance._pb_vals.get(self._name)

    def __set__(self, instance: "DbClient", value):
        instance._pb_vals[self._name] = value
        is_style = self._style_translate_table is not None
        if is_style:
            try:
                value = self._style_translate_table[value]
            except KeyError as e:
                raise TypeError("Incorrect type") from e
        instance._enqueued_update[f"progress_{instance.stage_for_progress}_{self._db_key}"] = value #value

        if (not is_style) and (instance.is_error is None):
            instance.is_error = False
        instance._schedule_update(immediatly=is_style)

    def __delete__(self, instance: "DbClient"):
        self.__set__(instance, None)





class DbClient():
    FLUSH_DELAY = 0.5

    current = PBProps("value")
    total = PBProps("max")
    msg = PBProps("msg")
    is_error = PBProps("style")

    def __init__(self, task_id: str, stage: str, q_id: str, stage_for_progress: str = None):
        self.task_id: str = task_id
        self.stage: str = stage
        self.stage_for_progress = stage_for_progress or stage
        self.q_id: str = q_id
        self.task_dir = DATA_PATH / task_id
        self.state_key = f"/tasks/{self.task_id}/state"
        self._pb_vals = {}

        self._enqueued_update = {}
        self._update_counter = 0
        self._flushed_update = 0

        self._update_flushed = asyncio.Condition()
        self._flush_task: asyncio.Task = asyncio.create_task(self._flush())
        self._flush_timer: asyncio.TimerHandle = None
        self._flush_event = asyncio.Event()

        self.task_dir.mkdir(exist_ok=True)


    def _schedule_update(self, immediatly=False):
        self._update_counter += 1
        if immediatly:
            self._flush_event.set()
        else:
            if not self._flush_timer:
                self._flush_timer = asyncio.get_running_loop().call_later(
                    self.FLUSH_DELAY,
                    self._flush_event.set
                )

    def __setitem__(self, key:str, value):
        if key.startswith("progress_"):
            raise ValueError("Should set progress only via properties")
        self._enqueued_update[key] = value
        self._schedule_update()

    async def __getitem__(self, key):
        if self._enqueued_update:
            # using transaction to flush updates and get cancelation status
            @self._transaction_after_flush
            async def tx(pipe:Pipeline):
                if isinstance(key, str):
                    pipe.hget(self.state_key, key)
                else:
                    pipe.hmget(self.state_key, *key)
            return (await tx)[-1]
        else:
            # no updated to flush, read operation doesn't require a transaction
            if isinstance(key, str):
                return await redis.hget(self.state_key, key)
            else:
                return await redis.hmget(self.state_key, *key)

    async def _wait_for_flush(self, tgt_upd):
        async with self._update_flushed:
            await self._update_flushed.wait_for(
                lambda: tgt_upd <= self._flushed_update
            )

    def pb_hide(self):
        self.is_error = None

    async def sync(self, flush=True):
        if self._update_counter == self._flushed_update:
            return
        tgt_upd = self._update_counter
        if flush:
            self._flush_event.set()

        done, _ = await asyncio.wait(
            (
                asyncio.create_task(self._wait_for_flush(tgt_upd)),
                self._flush_task, # if flush task is cancelled and the condition will never come true
            ),
            return_when=asyncio.FIRST_COMPLETED,
        )

        # If self._flush_task was cancelled - raise the error and unlock waiting threads
        for t in done:
            await t


    def substage(self, substage_name):
        return _create_db_client(self.task_id, self.stage, self.q_id, substage_name)

    async def check_if_cancelled(self, client=None):
        if client is None:
            client = redis
        if self.q_id != await client.hget(f"/tasks/{self.task_id}/running", self.stage):
            raise VersionChangedException()


    def _prepare_update(self, upd:dict):
        to_del = []
        progress_keys = {
            f"progress_{self.stage_for_progress}_value",
            f"progress_{self.stage_for_progress}_max",
            f"progress_{self.stage_for_progress}_msg",
            f"progress_{self.stage_for_progress}_style",
        }
        if any(k in upd for k in progress_keys):
            report_upd = progress_keys
            report_upd.update(upd.keys())
        else:
            report_upd = upd.keys()

        for k, v in upd.items():
            if v is None:
                to_del.append(k)
        for k in to_del:
            del upd[k]
        return upd, to_del, report_upd

    async def transaction(self, func: Callable[[Pipeline], Coroutine[Any, Any, None]]) -> Awaitable[list]:
        return await self._transaction(func)

    async def _transaction_after_flush(self, func: Callable[[Pipeline], Coroutine[Any, Any, None]]) -> Awaitable[list]:
        return await self._transaction(func, func_before_flush=False)

    async def _transaction(self, func, func_before_flush=True):
        async with self._update_flushed:
            flushing = bool(self._enqueued_update)
            if flushing:
                upd_ver = self._update_counter
                self._enqueued_update, upd = {}, self._enqueued_update
                if upd:
                    print("-> update", upd)
                    if upd.get("progress_heatmap_style") == 'error':
                        print(f'''progress_heatmap_style = error''', flush=True)
                        # asyncio.current_task().print_stack()
                    if upd.get("progress_tree_style") == 'error':
                        print(f'''progress_tree_style = error''', flush=True)
                        asyncio.current_task().print_stack()
                to_set, to_del, report_upd = self._prepare_update(upd)
            else:
                if func is None:
                    return

            async with redis.pipeline(transaction=True) as pipe:
                while True:
                    try:
                        await pipe.watch(f"/tasks/{self.task_id}/running")
                        await self.check_if_cancelled(client=pipe)
                        if func_before_flush:
                            if func is None:
                                pipe.multi()
                            else:
                                await func(pipe)
                                if not pipe.explicit_transaction:
                                    raise RuntimeError("Transaction func didn't start the transaction")
                        else:
                            pipe.multi()

                        if not flushing:
                            if not func_before_flush:
                                await func(pipe)
                            return await pipe.execute()

                        extra_commands = 0
                        if to_del:
                            extra_commands += 1
                            pipe.hdel(self.state_key, *to_del)
                        if to_set:
                            extra_commands += 1
                            pipe.hset(self.state_key, mapping=to_set)

                        extra_commands += 1
                        report_updates(self.task_id, *report_upd, redis_client=pipe)

                        if func_before_flush:
                            res = (await pipe.execute())[:-extra_commands]
                        else:
                            if func is not None:
                                await func(pipe)
                            res = (await pipe.execute())[extra_commands:]

                        self._flushed_update = upd_ver
                        self._update_flushed.notify_all()

                        if self._flush_timer:
                            self._flush_timer.cancel()
                        if self._update_counter > self._flushed_update:
                            self._flush_timer = asyncio.get_running_loop().call_later(
                                delay=self.FLUSH_DELAY,
                                callback=self._flush_event.set,
                            )
                        else:
                            self._flush_timer = None

                        return res
                    except WatchError:
                        continue

    async def _flush(self):
        while True:
            await self._flush_event.wait()
            self._flush_event.clear()
            if self._flush_timer:
                self._flush_timer.cancel()
                self._flush_timer = None

            if self._flushed_update==self._update_counter:
                continue
            await self.transaction(None)
            if self._flushed_update==self._update_counter:
                continue

            if not (self._flush_event.is_set() or self._flush_timer):
                self._flush_timer = asyncio.get_running_loop().call_later(
                    self.FLUSH_DELAY,
                    self._flush_event.set
                )


    async def report_error(self, message, cancel_rest=True):
        self._enqueued_update.pop(f"progress_{self.stage_for_progress}_msg", None)
        if self.is_error and self.msg:
            self.msg += f"; {message}"
        else:
            self.is_error = True
            self.msg = message

        if cancel_rest:
            # implicitly syncs
            @self.transaction
            async def tx(pipe: Pipeline):
                pipe.multi()
                cancel(self.task_id, self.stage, redis_client=pipe)
            await tx
        else:
            await self.sync()


def get_db() -> DbClient:
    return _db_var.get()

