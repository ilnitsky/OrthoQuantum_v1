
from pathlib import Path
import secrets

import flask

# TODO: change to something more proper
# data will be stored at DATA_PATH / "user_id"

DATA_PATH = Path.cwd() / "user_data"
DATA_PATH.mkdir(exist_ok=True)

def register():
    exc = None
    for _ in range(10):
        try:
            flask.session["USER_ID"] = secrets.token_hex(16)
            path().mkdir()
            break
        except Exception as e:
            exc = e
    else:
        raise RuntimeError("Failed to create a user dir") from exc

def is_logged_in() -> bool:
    try:
        if not path().exists():
            del flask.session["USER_ID"]
            return False
        return True
    except Exception:
        return False

def path() -> Path:
    """Returns the path appropriate to store user's files"""
    try:
        path = DATA_PATH / flask.session["USER_ID"]
    except Exception:
        raise RuntimeError("XXX user not logged in!")
    return path
