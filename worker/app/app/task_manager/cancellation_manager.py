import asyncio
from functools import wraps
import traceback

import aioredis
import aioredis.client

from .exceptions import VersionChangedException, ReportErrorException
from .db_client import DbClient, _db_var

from ..redis import redis, GROUP
from ..utils import decode_int, DEBUG



class CancellationManager():
    """"""
    def __init__(self):
        self._psub : aioredis.client.PubSub = None
        self._tasks : dict[tuple, asyncio.Task] = {}
        self._manager_task : asyncio.Task = None
        self._new_sub_event : asyncio.Event = None


    async def _manager(self):
        """Cancels tasks if the version in the db changed"""
        while True:
            if not self._psub.subscribed:
                self._new_sub_event.clear()
                await self._new_sub_event.wait()
            async for message in self._psub.listen():
                if message is None or message['type'] != 'message':
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
            self._new_sub_event = asyncio.Event()
        self._manager_task = asyncio.create_task(self._manager())
        await self._psub.__aenter__()
        return self


    async def __aexit__(self, exc_type, exc, tb):
        self._manager_task.cancel()
        try:
            await self._manager_task
        except asyncio.CancelledError:
            pass
        self._manager_task = None
        await self._psub.__aexit__(exc_type, exc, tb)

    def wrap_handler(self, func):
        """Wraps a queue handler

        1) transforms q_id, task_id, stage, version into a single DbClient instance
        2) Adds cancelation on db version modification
        """
        @wraps(func)
        async def wrapper(q_name, q_id, task_id, stage, version, **kwargs):
            db = DbClient(
                task_id=task_id,
                stage=stage,
                version=int(version),
            )
            _db_var.set(db)

            version_key = f"/tasks/{db.task_id}/stage/{db.stage}/version"
            version_sub = f"__keyspace@0__:{version_key}"
            key = (db.task_id, db.stage)
            await self._psub.subscribe(version_sub)
            self._new_sub_event.set()

            should_ack = True
            try:
                current_version = decode_int(await redis.get(version_key))
                if current_version != db.version:
                    # updated before we managed to launch the task
                    raise VersionChangedException()
                self._tasks[key] = asyncio.current_task()
                res = await func(**kwargs)
                return res
            except VersionChangedException:
                # cancelled by Db (version check in transaction) or just above this line
                if DEBUG:
                    print("VersionChangedException", task_id)
                raise
            except asyncio.CancelledError:
                if key in self._tasks:
                    # cancelled from outside, assume server error or restart
                    # don't ackgnowledge, trigger task re-delivery
                    should_ack = False
                # else: cancelled by cancellation manager, old version, do ackgnowledge
                if DEBUG:
                    print("CancelledError", task_id)
                raise
            except KeyboardInterrupt:
                should_ack = False
                if DEBUG:
                    print("KeyboardInterrupt", task_id)
                raise
            except ReportErrorException as e:
                await db.report_error(e.args[0])
                if DEBUG:
                    print("ReportErrorException", e.args)
            except Exception as e:
                traceback.print_exc()
                if DEBUG:
                    msg = f"Internal server error: {repr(e)}"
                else:
                    msg = "Internal server error"
                await db.report_error(msg)
                raise
            finally:
                self._tasks.pop(key, None)
                await self._psub.unsubscribe(version_sub)
                if should_ack:
                    async with redis.pipeline(transaction=True) as pipe:
                        pipe.xack(q_name, GROUP, q_id)
                        pipe.xdel(q_name, q_id)
                        await pipe.execute()
                try:
                    await db.flush_progress()
                except: # ignore any exceptions or cancelation attempts if arize
                    pass
        return wrapper

cancellation_manager = CancellationManager()