import time

from .async_executor import AsyncExecutor

@AsyncExecutor.in_thread(max_running=2)
def example_func(*args, **kwargs):
    print("START_T",args, kwargs)
    time.sleep(3)
    print("DONE_T", args, kwargs)

def _example_func2(*args, **kwargs):
    print("START_P",args, kwargs)
    time.sleep(5)
    print("DONE_P", args, kwargs)

example_func2 = AsyncExecutor.in_process(_example_func2, max_running=1)


"""
import contextvars

task_info = contextvars.ContextVar('task_info')
class ReportingQueue():
    def __init__(self, max_concurrent) -> None:
        self.max_concur = max_concurrent
        self.running = 0
        self.lock = asyncio.Lock()
        self.queue = deque()

    async def schedule(self, task_info):
        async with self.lock:
            if self.running < self.max_concur:
                pass # submit to pool immediately, return future
                self.running += 1
                return
            else:



        self.queue.


def limit(func=None, max_concurrent=5):
    if func is None:
        l = locals().copy()
        del l['func']
        return partial(limit, **l)

    q = ReportingQueue(max_concurrent=max_concurrent)
    @wraps(func)
    def wrapper(*args, **kwargs):
        q.
        pass
    return wrapper

async def process_table():
    tpe.submit(
        task_info.get(),
    )


asyncio.Semaphore()

async def start_work(data):



async def main():
    # await redis.set("/name", "bla")
    # print(await redis.get("/name"))
    # XADD /queue/task_queue * stage table taskid 123 version 2
    try:
        res = await redis.xgroup_create(QUEUE, GROUP, id="0", mkstream=True)
    except aioredis.ResponseError as e:
        # ignoring an error if the consumer group already exists
        if not e.args[0].startswith('BUSYGROUP'):
            raise

    async with redis as r:
        while True:
            res = await r.xreadgroup(GROUP, CONSUMER, {QUEUE: ">"}, count=1, block=3000)
            if not res:
                # Timeout, continue polling
                continue
            assert len(res) == 1, "Response contains multiple queues"
            queue_name, items = res[0]
            assert queue_name == QUEUE, "Response contains unknown queue"
            for id, data in items:
                # os.cpu_count()
                print(id)
                print(data)
                if data["stage"] == "table":
                    # build_table()
                    redis.set(f"/queue/working-tasks/{id}", ex=5)

            # [
            #     [
            #         '/queue/task_queue',
            #         [
            #             ('1620942295363-0',
            #                 {'kind': 'none'}
            #             ), (
            #                 '1620942569298-0',
            #                 {'f': 'v'}
            #             )
            #         ]
            #     ]
            # ]
    # XGROUP CREATE /queue/task_queue task_consumer_group 0 MKSTREAM
    # XADD /queue/task_queue * field value field value
    # XREADGROUP GROUP task_consumer_group worker-1 COUNT 20 BLOCK 50000 STREAMS /queue/task_queue ID 0


if __name__ == "__main__":
    asyncio.run(main())

"""