import asyncio
from asyncio import Future
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, Executor

from collections import deque
from functools import partial, wraps
from typing import Callable, Union

from itertools import chain

_IS_IN_PROCESS_POOL = False
def _process_pool_init():
    global _IS_IN_PROCESS_POOL
    _IS_IN_PROCESS_POOL = True

class _AsyncExecutor():
    def __init__(self, max_threads=None, max_processes=None, wait_for_futures=True):
        if _IS_IN_PROCESS_POOL:
            return
        self._tpe = ThreadPoolExecutor(max_workers=max_threads)
        self.max_threads = self._tpe._max_workers
        self._ppe = ProcessPoolExecutor(max_workers=max_processes, initializer=_process_pool_init)
        self.max_processes = self._ppe._max_workers
        self._loop = None
        self.wait_for_futures = wait_for_futures
        self._reinit = False
        self._queues : dict[Callable, deque[dict]] = {} # deque of _schedule_func args
        self._slots : dict[Callable, Union[int, float]] = {} # can schedule that many to run
        self._futures : dict[Future, Callable] = {} # executor future -> func
        self._proxy_futures : dict[Future, Future] = {} # executor future -> proxy future


    async def __aenter__(self):
        if _IS_IN_PROCESS_POOL:
            return
        self._loop = asyncio.get_running_loop()
        if self._reinit:
            self._tpe = ThreadPoolExecutor(max_workers=self.max_threads)
            self._ppe = ProcessPoolExecutor(max_workers=self.max_processes, initializer=_process_pool_init)

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if _IS_IN_PROCESS_POOL:
            return
        if self.wait_for_futures:
            futures = list(chain(self._futures.keys(), self._proxy_futures.values()))
            while futures:
                await asyncio.gather(
                    *futures,
                    return_exceptions=True,
                )
                futures = list(chain(self._futures.keys(), self._proxy_futures.values()))
        self._tpe.shutdown(wait=True, cancel_futures=True)
        self._ppe.shutdown(wait=True, cancel_futures=True)
        self._loop = None
        self._reinit = True


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

    def _exec_func(self, executor: Executor, func, args, kwargs, proxy_fut=None):
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

    def _exec(self, func, max_running, executor):
        if _IS_IN_PROCESS_POOL:
            return func
        self._queues[func] = deque()
        self._slots[func] = max_running or float('+inf')
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self._loop is None:
                raise RuntimeError(f"Can't schedule functions outside of AsyncExecutor 'async with' block")

            if self._slots[func] > 0:
                fut = self._exec_func(
                    executor=executor,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                )
                self._slots[func] -= 1
                return fut
            else:
                proxy_fut = Future(loop=self._loop)
                self._queues[func].append(dict(
                    executor=executor,
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    proxy_fut=proxy_fut,
                ))
                return proxy_fut
        return wrapper

    def in_thread(self, func=None, max_running=None, max_running_frac=None):
        if func is None:
            l = locals().copy()
            del l['func']
            del l['self']
            return partial(self.in_thread, **l)
        if max_running_frac is not None:
            max_running = round(self.max_threads * max_running_frac)
        return self._exec(executor=self._tpe, func=func, max_running=max_running)

    def in_process(self, func, max_running=None, max_running_frac=None) -> Callable:
        """
        Note: can't be used as a decorator due to pickle/multiprocessing interaction.
        Workaround example:
        def _cpu_work(length):
            for i in range(2**length):
                pass
        cpu_work = AsyncExecutor.in_process(_cpu_work, max_running=5)

        async def main():
            await cpu_work(30)
        """
        if max_running_frac is not None:
            max_running = round(self.max_processes * max_running_frac)
        return self._exec(executor=self._ppe, func=func, max_running=max_running)

AsyncExecutor = _AsyncExecutor()
