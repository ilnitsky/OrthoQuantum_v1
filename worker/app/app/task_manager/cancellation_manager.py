import asyncio
from collections.abc import Coroutine, Callable
from typing import Optional
import traceback

import aioredis


from .exceptions import VersionChangedException, ReportErrorException
from .db_client import DbClient

from ..redis import redis
from ..utils import decode_int, DEBUG



class CancellationManager():
    """"""
    def __init__(self):
        self._psub : aioredis.client.PubSub = None
        self._tasks : dict[tuple, Optional[asyncio.Task]] = {}
        self._manager_task : asyncio.Task = None
        self._cond : asyncio.Condition = None
        self._ack_tasks = set()


    async def _manager(self):
        """Cancels tasks if the version in the db changed"""
        while True:
            async with self._cond:
                await self._cond.wait_for(lambda: self._psub.subscribed)
            async for message in self._psub.listen():
                message = self._psub.handle_message(await self._psub.parse_response(block=True))
                if message is None:
                    continue
                if message['type'] != 'message':
                    continue
                # some key was incremented, trigger cancelation of the task
                # get key:
                path = message['channel'].split(":")[1].split("/")
                key = (path[2], path[4])
                task = self._tasks.pop(key, None)
                if task is None:
                    continue
                task.cancel("version changed")

    async def __aenter__(self):
        if self._psub is None:
            self._psub = redis.pubsub()
            self._cond = asyncio.Condition()
        self._manager_task = asyncio.create_task(self._manager())
        await self._psub.__aenter__()
        return self


    async def __aexit__(self, exc_type, exc, tb):
        self._manager_task.cancel()
        self._manager_task = None
        await self._psub.__aexit__(exc_type, exc, tb)

    def run_task(self, runnable: Coroutine, db: DbClient, *args, **kwargs):
        if not self._manager_task:
            raise RuntimeError("Can't schedule work outside of the context manager")
        return asyncio.create_task(self._run_task(runnable, db, *args, **kwargs))

    async def _run_task(self, runnable: Callable[..., Coroutine], db: DbClient, *args, **kwargs):
        version_key = f"/tasks/{db.task_id}/stage/{db.stage}/version"
        version_sub = f"__keyspace@0__:{version_key}"
        key = (db.task_id, db.stage)
        await self._psub.subscribe(version_sub)
        async with self._cond:
            self._cond.notify_all()

        should_ack = True
        try:
            current_version = decode_int(await redis.get(version_key))
            if current_version != db.version:
                # updated before we managed to launch the task
                raise VersionChangedException()
            self._tasks[key] = asyncio.current_task()
            return await runnable(*args, db=db, **kwargs)
        except VersionChangedException:
            # cancelled by Db (version check in transaction) or just above this line
            raise
        except asyncio.CancelledError:
            if key in self._tasks:
                # cancelled from outside, assume server error or restart
                # don't ackgnowledge, trigger re-delivery
                should_ack = False
            # else: cancelled by cancellation manager, old version, do ackgnowledge
            raise
        except KeyboardInterrupt:
            should_ack = False
            raise
        except ReportErrorException as e:
            await db.report_error(e.args[0])

        except Exception as e:
            if DEBUG:
                msg = f"Internal server error: {repr(e)}"
            else:
                msg = "Internal server error"
            await db.report_error(msg)
            traceback.print_exc()
            raise
        finally:
            await db.flush_progress()
            self._tasks.pop(key, None)
            if should_ack:
                await db.ack()
            await self._psub.unsubscribe(version_sub)
            async with self._cond:
                self._cond.notify_all()