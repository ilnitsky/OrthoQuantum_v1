import asyncio
from asyncio import Future
from asyncio.events import AbstractEventLoop
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, Executor
from concurrent.futures import Future as ConcurrentFuture
import threading

from functools import wraps
from typing import Awaitable, Callable, NamedTuple, Optional
from dataclasses import dataclass

from enum import Enum

_threadLocal = threading.local()
_threadLocal._is_in_async_pool = False

def _pool_init():
    _threadLocal._is_in_async_pool = True

class PoolKind(Enum):
    PROCESS = 1
    THREAD = 2

class ProgressFuture(Future):
    def __init__(self, *, loop: Optional[AbstractEventLoop]) -> None:
        super().__init__(loop=loop)
        self._progress_callback: Optional[Awaitable] = None
        self._progress_task: asyncio.Task = None
        self._position : int = None

    def _chain_future(self, parent: ConcurrentFuture):
        """Copy state of parent onto us, cancel parent if we are cancelled"""
        asyncio.futures._chain_future(parent, self)
        self.add_done_callback(self._cleanup)

        # self._report_progress(0)
        # add done listener to remove from the list

    def _cleanup(self, _):
        self._report_progress(-1)

    async def _run_progress_callback(self):
        if self._progress_callback is None:
            return
        pos = self._position
        self._progress_task = None
        await self._progress_callback(pos)
        if self._position == -1:
            self._progress_callback = None

    def _report_progress(self, pos):
        if self._position == pos:
            return
        self._position = pos

        if self._progress_callback is not None and self._progress_task is None:
            self._progress_task = self._loop.create_task(self._run_progress_callback())

    def set_progress_callback(self, callback:Optional[Awaitable]):
        self._progress_callback = callback
        if callback is not None and self._position is not None:
            self._progress_task = self._loop.create_task(self._run_progress_callback())


class Task(NamedTuple):
    id: int
    func_id: int
    future: ProgressFuture


@dataclass
class FuncQueue():
    func: Callable
    max_running: float
    max_pool_share: float
    slots: int = None # number of tasks to schedule


class AsyncPool():
    def __init__(self, kind:PoolKind):
        if kind not in PoolKind:
            raise RuntimeError(f"Unknown PoolKind: {kind}")
        self.kind = kind
        self.max_workers : int = None
        self.wait_on_exit = True
        self.cancel_unscheduled_on_exit = True

        self.executor : Executor = None
        self._loop = None

        self._funcs : list[FuncQueue] = []
        self._tasks : dict[int, Task] = {} # taskid, scheduled and running
        self._futures : dict[Future, int] = {} # taskid, scheduled and running
        self._tasks_queue : dict[int, tuple[list, dict]] = {} # taskid - args, kwargs, scheduled only

        self.task_id = 0
        self._schedule_handle = None

    def config(self, max_workers=None, wait_on_exit=True, cancel_unscheduled_on_exit=True):
        if self._in_pool:
            return
        if self._loop:
            raise RuntimeError("Can't configure while in use")
        if max_workers is not None:
            self.max_workers = max_workers
        if wait_on_exit is not None:
            self.wait_on_exit = wait_on_exit
        if cancel_unscheduled_on_exit is not None:
            self.cancel_unscheduled_on_exit = cancel_unscheduled_on_exit


    @property
    def _in_pool(self):
        return _threadLocal._is_in_async_pool

    def _schedule(self):
        self._schedule_handle = None
        pos = 1
        task_ids = iter(tuple(self._tasks_queue.keys()))
        if self._slots > 0:
            # schedule or report progress if unable to schedule
            for task_id in task_ids:
                task = self._tasks[task_id]
                func_ob = self._funcs[task.func_id]

                if func_ob.slots == 0:
                    # Can't schedule
                    task.future._report_progress(pos)
                    pos += 1
                    continue

                # Scheduling
                task.future._report_progress(0)
                args, kwargs = self._tasks_queue.pop(task_id)
                task.future._chain_future(
                    self.executor.submit(func_ob.func, *args, **kwargs)
                )
                func_ob.slots -= 1
                self._slots -= 1
                if self._slots == 0:
                    # can't schedule anymore, go to fast loop
                    break

        # unable to schdeule anymore, just report progress
        for task_id in task_ids:
            self._tasks[task_id].future._report_progress(pos)
            pos += 1

    def _future_done(self, future: ProgressFuture):
        task_id = self._futures.pop(future)
        task = self._tasks.pop(task_id)
        was_running = self._tasks_queue.pop(task_id, None) is None

        if was_running:
            self._funcs[task.func_id].slots += 1
            self._slots += 1

        if not self._schedule_handle:
            self._schedule_handle = self._loop.call_soon(self._schedule)


    async def __aenter__(self):
        if self._in_pool:
            raise RuntimeError("Nested AsyncExecutors are not allowed")
        self._loop = asyncio.get_running_loop()

        if self.kind is PoolKind.THREAD:
            executor = ThreadPoolExecutor
        else:
            executor = ProcessPoolExecutor

        self.executor = executor(max_workers=self.max_workers, initializer=_pool_init)
        self._slots = self.executor._max_workers
        for func in self._funcs:
            func.slots = round(max(
                min(func.max_running, func.max_pool_share*self._slots, self._slots),
                1
            ))

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.cancel_unscheduled_on_exit:
            for tid in self._tasks_queue:
                self._tasks[tid].future.cancel()
        if self.wait_on_exit:
            while self._futures:
                await asyncio.gather(
                    *self._futures.keys(),
                    return_exceptions=True,
                )
        self.executor.shutdown(wait=True, cancel_futures=True)

        self._loop = None
        self._tasks.clear()
        self._futures.clear()
        self._tasks_queue.clear()


    def _exec(self, max_running=float("+inf"), max_pool_share=1):
        def deco(func):
            if self._in_pool:
                # Only happens in process pool (thread doesn't re-execute decorators).
                # Return our target function, that way it would be called directly when the
                # wrapper is scheduled in the process pool
                return func
            @wraps(func)
            def wrapper(*args, **kwargs):
                if self._in_pool:
                    return func(*args, **kwargs)
                # now have access to func_id and target_func from outter scope
                if self._loop is None:
                    raise RuntimeError("Can't schedule functions outside of AsyncExecutor 'async with' block")
                fut = ProgressFuture(loop=self._loop)
                fut.add_done_callback(self._future_done)
                task = Task(id=self.task_id, func_id=func_id, future=fut)
                self.task_id += 1
                func_ob = self._funcs[func_id]
                if self._slots and func_ob.slots:
                    # can run right now
                    fut._report_progress(0)
                    fut._chain_future(
                        self.executor.submit(
                            target_func,
                            *args, **kwargs,
                        )
                    )

                    func_ob.slots -= 1
                    self._slots -= 1
                else:
                    # enqueue
                    self._tasks_queue[task.id] = (args, kwargs)
                    fut._report_progress(len(self._tasks_queue))
                self._futures[fut] = task.id
                self._tasks[task.id] = task
                return fut

            if self.kind is PoolKind.THREAD:
                # We don't have to schedule globally-accessible function in the thread pool
                # so we are scheduling the target function immediatly
                target_func = func
            else:
                # We have to schedule globally-accessible function in the the process pool
                # Target function (func) would be replaced by the scheduler function (wrapper),
                # that's why we're scheduling it
                # When this decorator re-runs inside of the process pool it would return
                # func instead of the wrapper (first condition in this function)
                # This means scheduling "wrapper" outside of the process pool results in the execution
                # of "func" inside of the process pool. Kinda mindblowing, but that's multiprocessing for you...
                target_func = wrapper

            func_id = len(self._funcs)
            self._funcs.append(FuncQueue(
                func=target_func,
                max_running=max_running,
                max_pool_share=max_pool_share,
            ))

            return wrapper
        return deco


class AsyncExecutor():
    def __init__(self):
        self._atp = AsyncPool(PoolKind.THREAD)
        self._app = AsyncPool(PoolKind.PROCESS)
        self.in_thread = self._atp._exec
        self.in_process = self._app._exec

    def config(self, max_threads=None, max_processes=None, wait_on_exit=None, cancel_unscheduled_on_exit=None):
        self._atp.config(max_workers=max_threads, wait_on_exit=wait_on_exit, cancel_unscheduled_on_exit=cancel_unscheduled_on_exit)
        self._app.config(max_workers=max_processes, wait_on_exit=wait_on_exit, cancel_unscheduled_on_exit=cancel_unscheduled_on_exit)


    async def __aenter__(self):
        await asyncio.gather(
            self._atp.__aenter__(),
            self._app.__aenter__(),
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await asyncio.gather(
            self._atp.__aexit__(exc_type, exc, tb),
            self._app.__aexit__(exc_type, exc, tb),
        )


async_pool = AsyncExecutor()
async_pool.config(max_threads=100)