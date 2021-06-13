import asyncio
from dataclasses import dataclass
from typing import Union, Callable, Coroutine
import traceback

from .cancellation_manager import cancellation_manager
from ..redis import redis, GROUP, CONSUMER

@dataclass
class QueueInfo():
    slots_left: Union[int, float]
    last_id: str
    handler: Coroutine
    _done_callback: Callable

class QueueManager():
    def __init__(self):
        self.queues : dict[str, QueueInfo] = {}
        self.update_listening_queues = asyncio.Event()
        self.update_listening_queues.set()
        self.running_tasks = set()
        self._in_context_manager = False

    def add_handler(self, queue_name, max_running=float("+inf")):
        """
        Adds a function that handles every item received by the queue
        function must have signature func(queue_name, q_id, **data)
        where q_id is the ID of the function in the queue and the **data is queue data
        """
        def deco(func):
            def done_callback(task):
                try:
                    self.running_tasks.remove(task)
                    q = self.queues[queue_name]
                    if q.slots_left == 0:
                        self.update_listening_queues.set()
                    q.slots_left += 1
                except KeyError:
                    pass

            self.queues[queue_name] = QueueInfo(
                slots_left=max_running,
                last_id="0",
                handler=func,
                _done_callback=done_callback,
            )
            return func
        return deco

    async def __aenter__(self):
        self._in_context_manager = True
        await cancellation_manager.__aenter__()
        print(f"listening on {', '.join(self.queues.keys())}")

    async def __aexit__(self, exc_type, exc, tb):
        await cancellation_manager.__aexit__(exc_type, exc, tb)
        self._in_context_manager = False
        while self.running_tasks:
            await asyncio.wait(self.running_tasks, return_when=asyncio.ALL_COMPLETED)


    async def __call__(self):
        if not self._in_context_manager:
            raise RuntimeError("Must use within a context manager")
        # Creating consumer groups for all queues queue (if doesn't already exist)
        async with redis.pipeline(transaction=False) as pipe:
            for queue_name in self.queues:
                pipe.xgroup_create(queue_name, GROUP, id="0", mkstream=True)
            await pipe.execute(raise_on_error=False)

        async with redis as r:
            queue_list = {}
            while True:
                max_count = 30 # max jobs to receive per loop
                has_full_queues = False
                if self.update_listening_queues.is_set():
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

                    for q_id, data in items:
                        print("Enqueueing", queue_name, q_id, data)

                        try:
                            task = asyncio.create_task(
                                q.handler(queue_name, q_id, **data),
                            )
                        except Exception as e:
                            print("Error while enqueueing task, task skipped")
                            traceback.print_exc()
                            await redis.xack(queue_name, GROUP, q_id)
                            continue
                        q.slots_left -= 1
                        self.running_tasks.add(task)
                        task.add_done_callback(q._done_callback)

                    if q.slots_left <= 0:
                        self.update_listening_queues.set()



queue_manager = QueueManager()