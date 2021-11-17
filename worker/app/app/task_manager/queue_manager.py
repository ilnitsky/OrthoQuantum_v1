import asyncio
from dataclasses import dataclass, field
from typing import Union, Coroutine
import anyio
from anyio.abc import TaskGroup
import traceback

from .db_client import _create_db_client
from .exceptions import VersionChangedException
from ..utils import DEBUG

from aioredis.client import PubSub

from ..redis import redis, GROUP, CONSUMER, launch, finish, ack

DB_CANCEL_REASON = "Canceled by DB"

@dataclass
class QueueInfo():
    name: str
    raw: bool
    slots_left: Union[int, float]
    handler: Coroutine
    last_id: str = "0-0"
    cancel_scopes:dict[str, anyio.CancelScope] = field(default_factory=dict)

class QueueManager():
    def __init__(self):
        self.queues : dict[str, QueueInfo] = {}
        self.update_listening_queues = asyncio.Event()
        self.update_listening_queues.set()
        self.qid_2_task :dict[str, asyncio.Task]= {}
        self.task_2_qid :dict[asyncio.Task, str]= {}
        self._pubsub_task: asyncio.Task = None
        self._in_context_manager = False
        self._finished_tasks = asyncio.Queue()

    def add_handler(self, queue_name, raw_data=False, max_running=float("+inf")):
        """
        Adds a function that handles every item received by the queue
        if raw_data is True:
            called with (queue_name, q_id, **data)
        if raw_data is False:
            called with (**data) (excluding stage and task_id)
            an instance of DbClient is created
        function must have signature func(queue_name, q_id, **data)
        where q_id is the ID of the function in the queue and the **data is queue data
        """
        def deco(func):
            self.queues[queue_name] = QueueInfo(
                name=queue_name,
                raw=raw_data,
                slots_left=max_running,
                handler=func,
            )
            return func
        return deco

    async def _canceler(self):
        async with redis.pubsub(ignore_subscribe_messages=True) as pubsub:
            await pubsub.subscribe("/canceled_jobs")
            async for message in pubsub.listen():
                try:
                    queue_name, q_id = message["data"].rsplit(":", maxsplit=1)
                    self.queues[queue_name].cancel_scopes[q_id].cancel()
                except Exception:
                    continue

    async def _run(self, q:QueueInfo, q_id:str, data:dict[str, str], scope:anyio.CancelScope):
        print("_run", q, q_id, data)
        should_ack = True
        task_id, stage = None, None
        with scope:
            try:
                if scope.cancel_called:
                    return
                if q.raw:
                    await q.handler(q.name, q_id, **data)
                else:
                    should_ack = False
                    task_id = data.pop("task_id")
                    stage = data.pop("stage")
                    if not await launch(task_id=task_id, stage=stage, q_id=q_id):
                        if DEBUG:
                            print("Unable to start, was cancelled")
                        raise VersionChangedException()
                    async with _create_db_client(task_id=task_id, stage=stage, q_id=q_id):
                        print("*** db client created, q.handler", q_id)
                        await q.handler(**data)
                        print("*** q.handler exit", q_id)

                # successful exit
                should_ack = True

            except VersionChangedException:
                # cancelled by Db (version check in transaction) or just above this line
                if DEBUG:
                    print(f"VersionChangedException on {stage} of {task_id} ({q_id} on {q.name})")
                should_ack = True
            except KeyboardInterrupt:
                if DEBUG:
                    print(f"KeyboardInterrupt on {stage} of {task_id} ({q_id} on {q.name})")
                should_ack = False
                raise
            except Exception:
                should_ack = True
                print(f"Exception on {stage} of {task_id} ({q_id} on {q.name})")
                traceback.print_exc()
            finally:
                del q.cancel_scopes[q_id]

                if q.slots_left == 0:
                    self.update_listening_queues.set()
                q.slots_left += 1

                with anyio.CancelScope(shield=True):
                    print(f"pipeline")
                    async with redis.pipeline(transaction=True) as pipe:
                        if not q.raw:
                            finish(task_id, stage, q_id, redis_client=pipe)
                        if should_ack:
                            ack(q.name, q_id, pipe)
                        await pipe.execute()


    async def _scheduler(self, tg:TaskGroup):
        print(f"listening on {', '.join(self.queues.keys())}")
        # Creating consumer groups for all queues queue (if doesn't already exist)
        async with redis.pipeline(transaction=False) as pipe:
            for queue_name in self.queues:
                pipe.xgroup_create(queue_name, GROUP, id="0", mkstream=True)
            await pipe.execute(raise_on_error=False)

        to_ack = []
        async with redis as r:
            queue_list = {}
            while True:
                if self.update_listening_queues.is_set():
                    max_count = 30 # max jobs to receive per loop
                    has_full_queues = False
                    queue_list.clear()
                    for q_name, q in self.queues.items():
                        if q.slots_left > 0:
                            queue_list[q_name] = q.last_id
                            max_count = min(max_count, q.slots_left)
                        else:
                            has_full_queues = True
                    self.update_listening_queues.clear()

                if not queue_list:
                    # no listen queues are ready to receive items
                    await self.update_listening_queues.wait()
                    continue

                res = await r.xreadgroup(
                    GROUP, CONSUMER, queue_list,
                    count=max_count, block=1000 if has_full_queues else 120000,
                )
                # using block=1000 to allow changing queue_list once per second
                # so a second after a slot opens up we are listening for the respective queue

                if not res:
                    # Timeout, continue polling
                    continue

                for queue_name, items in res:
                    q = self.queues[queue_name]
                    if q.last_id != ">":
                        self.update_listening_queues.set()
                        if not items:
                            # processed all of the unACKnowledged messages, go to longpoll
                            q.last_id = ">"
                        else:
                            # next time sending the last item's ID
                            q.last_id = items[-1][0]
                    if not items:
                        continue


                    for q_id, data in items:
                        if not data:
                            print(f"Skipping {q_id} (xdel'ed from DB)")
                            to_ack.append(q_id)
                            continue
                        print("Enqueueing", q.name, q_id, data)
                        scope = anyio.CancelScope()
                        q.cancel_scopes[q_id] = scope
                        tg.start_soon(
                            self._run,
                            q, q_id, data, scope
                        )
                        q.slots_left -= 1

                    if to_ack:
                        tg.start_soon(redis.xack, q.name, GROUP, *to_ack)
                        to_ack.clear()

                    if q.slots_left <= 0:
                        self.update_listening_queues.set()


    async def listen(self):
        async with anyio.create_task_group() as tg:
            tg.start_soon(self._scheduler, tg)
            tg.start_soon(self._canceler)



queue_manager = QueueManager()