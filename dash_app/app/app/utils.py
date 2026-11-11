from dash import callback_context, no_update
from dash.dependencies import Input, Output, State, DashDependency
import os

def clamp(min_val, cur_val, max_val):
    return min(max(min_val, cur_val), max_val)


def parse_int(val, default:int):
    try:
        return int(val)
    except Exception:
        return default

def parse_float(val, default:float):
    try:
        return float(val)
    except Exception:
        return default

def decode_int(*items:bytes, default=0) -> int:
    if len(items)==1:
        return int(items[0]) if items[0] else default

    return map(
        lambda x: int(x) if x else default,
        items,
    )


class DashProxy():
    def __init__(self, args):
        self._data = {}
        self._input_order = []
        self._output_order = []
        self._outputs = {}
        self.triggered = set()


        for arg in args:
            if not isinstance(arg, DashDependency):
                continue
            k = (arg.component_id, arg.component_property)

            if isinstance(arg, (Input, State)):
                self._input_order.append(k)
            elif isinstance(arg, Output):
                self._output_order.append(k)
            else:
                raise RuntimeError("Unknown DashDependency")

    def is_triggered_by(self, *args):
        return any(arg in self.triggered for arg in args)

    @property
    def first_load(self):
        return not self.triggered

    def __getitem__(self, key):
        if key in self._outputs:
            return self._outputs[key]
        try:
            return self._data[key]
        except KeyError as e:
            raise RuntimeError("Key not found, missing dash input/state?") from e


    def __setitem__(self, key, value):
        self._outputs[key] = value

    def _enter(self, args):
        for k, val in zip(self._input_order, args):
            self._data[k] = val
        triggers = callback_context.triggered

        self.triggered.clear()
        if not(len(triggers) == 1 and triggers[0]['prop_id'] == "."):
            self.triggered.update(
                tuple(item['prop_id'].rsplit('.', maxsplit=1))
                for item in callback_context.triggered
            )

    def _exit(self):
        res = tuple(
            self._outputs.get(k, no_update)
            for k in self._output_order
        )

        self._outputs.clear()
        self._data.clear()
        self.triggered.clear()
        if len(res) == 1:
            return res[0]
        else:
            return res


class DashProxyCreator():
    def __init__(self, dash_app):
        self.dash_app = dash_app
        # self.callback = wraps(dash_app.callback)(self.callback)

    def callback(self, *args, **kwargs):
        def deco(func):
            dp = DashProxy(args)
            def wrapper(*args2):
                dp._enter(args2)
                func(dp)
                return dp._exit()
            return self.dash_app.callback(*args, **kwargs)(wrapper)
        return deco

DEBUG = bool(os.environ.get('DEBUG', '').strip())