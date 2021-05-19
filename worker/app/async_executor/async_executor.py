import asyncio
from asyncio import Future
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from collections import deque, namedtuple
from functools import wraps
from typing import Callable, NamedTuple, Union
from dataclasses import dataclass
from itertools import chain, count

_IS_IN_PROCESS_POOL = False
def _process_pool_init():
    global _IS_IN_PROCESS_POOL
    _IS_IN_PROCESS_POOL = True

class Task(NamedTuple):
    id: int
    args: list
    kwargs: dict

import heapq

@dataclass
class FuncQueue():
    func: Callable
    queue: dict[int, Task]
    slots: int # number of tasks to schedule
    max_running: float

class AsyncPool():
    def __init__(self, max_workers=None, wait_on_exit=True):
        self.wait_on_exit = wait_on_exit

        self.executor = self._create_executor(max_workers)
        self.max_workers = self.executor._max_workers
        self._slots = self.max_workers

        self._next_queue_heap = []

        self._funcs : list[FuncQueue] = []
        self._futures : dict[Future, tuple] = {}
        self.task_id = count()

    def _create_executor(self, max_workers):
        return ThreadPoolExecutor(max_workers=max_workers)

    def _exec_func(self, func_id, args, kwargs, proxy_fut=None):
        func = self._funcs[func_id].func
        fut = asyncio.wrap_future(
            self.executor.submit(func, *args, **kwargs),
            loop=self._loop,
        )
        if proxy_fut:
            self._proxy_futures[fut] = proxy_fut
            fut.add_done_callback(self._mirror_future_state)
        self._futures[fut] = func
        fut.add_done_callback(self._executor_done_callback)
        return fut

    def _proxy_future_cancel(self, fut:Future):
        if not fut.cancelled():
            return
        if fut not in self._futures:
            return
        func_id, del_task_id = self._futures.pop(fut)

        found = False
        for new_pos, (task_id, task) in enumerate(self._funcs[func_id].queue.items(), start=0):
            if found:
                task.notify(new_pos)
            elif task_id == del_task_id:
                found = True

        del self._funcs[func_id].queue[del_task_id]




    def _exec(self, func, max_running=float("+inf")):
        func_id = len(self._funcs)
        self._funcs.append(FuncQueue(
            func=func,
            queue=dict(),
            max_running=max_running,
            slots=max_running,
        ))
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self._loop is None:
                raise RuntimeError(f"Can't schedule functions outside of AsyncExecutor 'async with' block")

            if self._slots and self._funcs[func_id].slots:
                # can schedule right now
                return self._exec_func(func_id, args, kwargs)
            else:
                # enqueue
                task = Task(next(self.task_id), args, kwargs)
                if not self._funcs[func_id].queue:
                    # we're the first element in this queue
                    # add to _next_queue_heap
                    heapq.heappush(self._next_queue_heap, (task.id, func_id))
                self._funcs[func_id].queue[task.id] = task
                proxy_fut = Future(loop=self._loop)
                self._futures[proxy_fut] = (func_id, task.id)
                proxy_fut.add_done_callback(self._proxy_future_cancel)



            if self._slots[func] > 0:
                fut = self._exec_func(
                    run_in_process=run_in_process,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                )
                self._slots[func] -= 1
                return fut
            else:
                proxy_fut = Future(loop=self._loop)
                self._queues[func].append(dict(
                    run_in_process=run_in_process,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    proxy_fut=proxy_fut,
                ))
                return proxy_fut
        return wrapper


class AsyncExecutor():
    def __init__(self, max_threads=None, max_processes=None, wait_on_exit=True):
        self.wait_on_exit = wait_on_exit
        self.max_threads = max_threads
        self.max_processes = max_processes

        self._tpe_slots = 0
        self._ppe_slots = 0

        self._tpe = None
        self._ppe = None
        self._loop = None

        self._next_queue_heap = []

        self._func_id = count()
        self._job_id = count()

        # self._queues : dict[Callable, deque[dict]] = {} # deque of _schedule_func args
        self._queues : list[deque[dict]] = {} # deque of _schedule_func args
        self._limits : dict[Callable, tuple[_NUMBER, _NUMBER]] = {} # limits of parallel execution
        self._slots : dict[Callable, _NUMBER] = {} # can schedule that many instances to run
        self._futures : dict[Future, Callable] = {} # executor future -> func
        self._proxy_futures : dict[Future, Future] = {} # executor future -> proxy future


    async def __aenter__(self):
        if _IS_IN_PROCESS_POOL:
            raise RuntimeError("Nested AsyncExecutors are not allowed")
        self._loop = asyncio.get_running_loop()

        self._tpe = ThreadPoolExecutor(max_workers=self.max_threads)
        self.max_threads = self._tpe._max_workers
        self._tpe_slots = self.max_threads

        self._ppe = ProcessPoolExecutor(max_workers=self.max_processes, initializer=_process_pool_init)
        self.max_processes = self._ppe._max_workers
        self._ppe_slots = self.max_processes

        for func, (max_running, max_running_frac, is_thread) in self._limits.items():
            self._slots[func] = max(
                min(
                    max_running,
                    round(
                        max_running_frac *
                        (self.max_threads if is_thread else self.max_processes)
                    )
                ),
                1,
            )
            self._queues[func] = deque()

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.wait_on_exit:
            futures = list(chain(self._futures.keys(), self._proxy_futures.values()))
            while futures:
                await asyncio.gather(
                    *futures,
                    return_exceptions=True,
                )
                futures = list(chain(self._futures.keys(), self._proxy_futures.values()))
        self._tpe.shutdown(wait=True, cancel_futures=True)
        self._tpe = None
        self._ppe.shutdown(wait=True, cancel_futures=True)
        self._ppe = None
        self._loop = None
        self._queues.clear()
        self._slots.clear()
        self._futures.clear()
        self._proxy_futures.clear()


    def _mirror_future_state(self, fut: Future):
        proxy_fut = self._proxy_futures.pop(fut)
        proxy_fut : Future
        try:
            proxy_fut.set_result(fut.result())
        except asyncio.CancelledError:
            proxy_fut.cancel()
        except asyncio.InvalidStateError:
            raise
        except Exception as e:
            proxy_fut.set_exception(e)

    def _future_done_callback(self, fut: Future):
        func = self._futures.pop(fut)
        q = self._queues[func]
        q : deque
        if q:
            # schedule next
            self._exec_func(**q.popleft())
        else:
            self._slots[func] += 1

    def _exec_func(self, run_in_process, func, args, kwargs, proxy_fut=None):
        executor = self._ppe if run_in_process else self._tpe
        fut = asyncio.wrap_future(
            executor.submit(func, *args, **kwargs),
            loop=self._loop,
        )
        if proxy_fut:
            self._proxy_futures[fut] = proxy_fut
            fut.add_done_callback(self._mirror_future_state)
        self._futures[fut] = func
        fut.add_done_callback(self._future_done_callback)
        return fut

    def _exec(self, func, run_in_process):
        func_id = len(self._queues)
        self._queues.append(deque())
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self._loop is None:
                raise RuntimeError(f"Can't schedule functions outside of AsyncExecutor 'async with' block")

            if self._slots[func] > 0:
                fut = self._exec_func(
                    run_in_process=run_in_process,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                )
                self._slots[func] -= 1
                return fut
            else:
                proxy_fut = Future(loop=self._loop)
                self._queues[func].append(dict(
                    run_in_process=run_in_process,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    proxy_fut=proxy_fut,
                ))
                return proxy_fut
        return wrapper

    def in_thread(self, max_running=float("+inf"), max_running_frac=1):
        if _IS_IN_PROCESS_POOL:
            return lambda func: func
        def deco(func):
            self._limits[func] = (max_running, max_running_frac, True)
            return self._exec(run_in_process=False, func=func)
        return deco

    def in_process(self, max_running=float("+inf"), max_running_frac=1) -> Callable:
        if _IS_IN_PROCESS_POOL:
            return lambda func: func
        def deco(func):
            self._limits[func] = (max_running, max_running_frac, False)
            return self._exec(run_in_process=True, func=func)
        return deco

