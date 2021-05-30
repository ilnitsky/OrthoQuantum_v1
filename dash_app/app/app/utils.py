from functools import wraps
from dash import callback_context, no_update
from dash.dependencies import Input, Output, State, DashDependency

QUEUE = "/queue/task_queue"
GROUP = "worker_group"

def decode_int(*items:bytes, default=0) -> int:
    if len(items)==1:
        return int(items[0]) if items[0] else default

    return map(
        lambda x: int(x) if x else default,
        items,
    )


class _DashProxy():
    def __init__(self, args):
        self._data = {}
        self._input_order = []
        self._output_order = []
        self._outputs = {}
        self.triggered = None
        self.first_load = False
        self.triggered : set

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

    def __getitem__(self, key):
        if key in self._outputs:
            return self._outputs[key]
        return self._data[key]

    def __setitem__(self, key, value):
        self._outputs[key] = value

    def enter(self, args):
        for k, val in zip(self._input_order, args):
            self._data[k] = val
        triggers = callback_context.triggered

        if len(triggers) == 1 and triggers[0]['prop_id'] == ".":
            self.first_load = True
            self.triggered = set()
        else:
            self.triggered = set(
                tuple(item['prop_id'].rsplit('.', maxsplit=1))
                for item in callback_context.triggered
            )

    def exit(self):
        res = tuple(
            self._outputs.get(k, no_update)
            for k in self._output_order
        )

        self._outputs.clear()
        self._data.clear()
        self.triggered.clear()

        return res


class DashProxy():
    def __init__(self, dash_app):
        self.dash_app = dash_app
        # self.callback = wraps(dash_app.callback)(self.callback)

    def callback(self, *args, **kwargs):
        def deco(func):
            dp = _DashProxy(args)
            def wrapper(*args2):
                dp.enter(args2)
                func(dp)
                return dp.exit()
            return self.dash_app.callback(*args, **kwargs)(wrapper)
        return deco