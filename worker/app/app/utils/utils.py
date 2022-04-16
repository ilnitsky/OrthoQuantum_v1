import abc
import os
import contextlib
import tempfile
import json
import itertools
import time
from functools import partial, wraps
from pathlib import Path
from collections import Counter
import anyio
def benchmark(func):
    @wraps(func)
    def deco(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print(f"Function {func.__name__} took {time.perf_counter()-start:.4f}s")
    return deco

def decode_int(*items, default=0) -> int:
    if len(items)==1:
        return int(items[0]) if items[0] else default

    return map(
        lambda x: int(x) if x else default,
        items,
    )


DEBUG = bool(os.environ.get('DEBUG', '').strip())
DATA_PATH = Path.cwd() / "user_data"

@contextlib.contextmanager
def atomic_file(file:Path):
    fd, tmp = tempfile.mkstemp(
        suffix=f'.{file.name}',
        dir=file.parent,
    )
    try:
        os.close(fd)
        yield tmp
        os.replace(tmp, file)
    except:
        os.unlink(tmp)
        raise


def _if_exists(path, flags):
    flags &= ~os.O_CREAT
    return os.open(path, flags)

open_existing = partial(open, opener=_if_exists)

def json_minify(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))

class DelayStrategy(abc.ABC):
    @abc.abstractmethod
    def __iter__(self):
        pass

class ExponentialBackoff(DelayStrategy):
    def __init__(self, init_delay=0.2, max_delay=5, mult=2):
        self.init_delay = init_delay
        self.max_delay = max_delay
        self.mult = mult

    def __iter__(self):
        cur_delay = self.init_delay
        while True:
            yield cur_delay
            cur_delay = min(self.max_delay, cur_delay*self.mult)



class RetiesFailed(Exception):
    pass

def retry(func=None, /, call_timeout=None, total_timeout=None, retries=3, delay_strategy: DelayStrategy=ExponentialBackoff(), retriable_exceptions=(Exception,)):
    if func is None:
        kwargs = dict(locals())
        kwargs.pop("func")
        def deco(func):
            return retry(func, **kwargs)
        return deco
    @wraps(func)
    async def wrapper(*args, **kwargs):
        with anyio.fail_after(total_timeout):
            exc = None
            try:
                with anyio.fail_after(call_timeout):
                    return await func(*args, **kwargs)
            except TypeError:
                raise # something wrong with func args
            except BaseException as e:
                if not isinstance(e, retriable_exceptions):
                    raise
                __import__("traceback").print_exc()
                exc = e
            for delay in itertools.islice(delay_strategy, retries):
                if delay:
                    await anyio.sleep(delay)
                try:
                    with anyio.fail_after(call_timeout):
                        return await func(*args, **kwargs)
                except BaseException as e:
                    if not isinstance(e, retriable_exceptions):
                        raise
                    __import__("traceback").print_exc()
                    exc = e
            raise RetiesFailed(f'Calling "{func.__qualname__}" failed after {retries} retries') from exc
    return wrapper

def case_insensitive_unique(data):
    seen = set()
    for item in data:
        mod_item = item.strip().lower()
        if mod_item in seen:
            continue
        seen.add(mod_item)
        yield item

def case_insensitive_top_trunc(data, n=5, fraction=0.8):
    data_len = 0
    def process(elem):
        nonlocal data_len
        data_len += 1
        return elem.strip().upper()

    cnt = Counter(map(process, data))
    if data_len == 0:
        return '<NA in selected species>'

    res = []
    if data_len<10:
        frac = data_len
    else:
        frac = fraction*data_len
    included_count = 0
    for elem, count in cnt.most_common(n):
        res.append(elem)
        included_count += count
        if included_count >= frac:
            break
    else:
        res.append('...')

    return ', '.join(res)