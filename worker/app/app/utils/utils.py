from functools import partial
import os
from typing import Text
from pathlib import Path
import contextlib
import tempfile

def decode_int(item:Text, default=0) -> int:
    res = default
    try:
        res = int(item)
    except Exception:
        pass
    return res

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
    except:
        os.unlink(tmp)
        raise
    else:
        os.replace(tmp, file)

def _if_exists(path, flags):
    flags &= ~os.O_CREAT
    return os.open(path, flags)

open_existing = partial(open, opener=_if_exists)