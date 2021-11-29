from functools import partial
import os
from typing import Text
from pathlib import Path
import contextlib
import tempfile
import json

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