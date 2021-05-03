import os
import os.path
import time
import json
import secrets

import urllib.parse as urlparse
from dash import Dash, callback_context, no_update
from dash.dependencies import Input, Output, State, DashDependency
import dash_table
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import redis
import flask

import celery

from phydthree_component import PhydthreeComponent

from .app import SPARQL_wrap, presence_img, correlation_img

from . import layout
from . import user

from functools import partial, wraps
import sys

# print= partial(print, file=sys.stderr, flush=True)


app = flask.Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

# external JavaScript files
external_scripts = [
    {
        'src': 'https://code.jquery.com/jquery-2.2.4.min.js',
        'integrity': 'sha256-BbhdlvQf/xTY9gja0Dq3HiwQF8LaCRTXxZKRutelT44=',
        'crossorigin': 'anonymous'
    },
    # {
    #     'src': 'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js',
    #     'integrity': 'sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa',
    #     'crossorigin': 'anonymous'
    # },
    {
        'src': 'https://d3js.org/d3.v3.min.js',
        # 'integrity': 'sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa',
        # 'crossorigin': 'anonymous'
    },
]
# external CSS stylesheets
external_stylesheets = [
    # {
    #     'href': 'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css',
    #     'rel': 'stylesheet',
    #     'integrity': "sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u",
    #     'crossorigin': 'anonymous'
    # },
    # {
    #     'href': 'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap-theme.min.css',
    #     'rel': 'stylesheet',
    #     'integrity': "sha384-rHyoN1iRsVXV4nD0JutlnGaslCJuC7uwjduW9SVrLvRYooPp2bWYgmgJQIXwl/Sp",
    #     'crossorigin': 'anonymous'
    # },
    dbc.themes.UNITED,
]


dash_app = Dash(__name__, server=app, suppress_callback_exceptions=True, external_scripts=external_scripts, external_stylesheets=external_stylesheets)
dash_app.layout = layout.index

def login(dst):
    # TODO: dsiplay login layout, login, redirect to the original destintation
    user.register()
    return dcc.Location(pathname=dst, id="some_id", hash="1", refresh=True)

def new_task():
    user_id = flask.session["USER_ID"]
    t = int(time.time())
    for _ in range(100):
        task_id = secrets.token_hex(16)
        res = user.db.msetnx({
            f"/tasks/{task_id}/user_id": user_id,
            f"/tasks/{task_id}/created": t,
            f"/tasks/{task_id}/accessed": t,
        })
        if res:
            break
    else:
        raise RuntimeError("Failed to create a unique task_id")

    # Possible race condition, task_counter is only for statistics and ordering
    task_no = user.db.incr(f"/users/{user_id}/task_counter")
    user.db.set(f"/tasks/{task_id}/name", f"Request {task_no}")

    # Publishes the task to the system, must be the last action
    user.db.rpush(f"/users/{user_id}/tasks", task_id)

    return task_id

def get_task(task_id):
    """Checks that task_id is valid and active, sets /accessed date to current"""
    if '/' in task_id:
        return False
    res = user.db.set(f"/tasks/{task_id}/accessed", int(time.time()), xx=True)
    return res



@dash_app.callback(
    Output('page-content', 'children'),
    Output('location', 'search'),
    Input('location', 'href'),
)
def router_page(href):
    url = urlparse.urlparse(href)
    pathname = url.path.rstrip('/')
    search = f'?{url.query}'

    if pathname == '/dashboard':
        if not user.is_logged_in():
            return login(pathname), search

        args = urlparse.parse_qs(url.query)
        for arg in args:
            args[arg] = args[arg][0]

        create_task = True
        if 'task_id' in args:
            create_task = not get_task(args['task_id'])

        if create_task:
            args['task_id'] = new_task()
            search = f"?{urlparse.urlencode(args)}"

        return layout.dashboard(args['task_id']), search
    if pathname == '/reports':
        return layout.reports, search
    if pathname == '/blast':
        return layout.blast, search

    return '404', search


# TODO: need this?
@dash_app.callback(Output('dd-output-container', 'children'), [Input('dropdown', 'value')])
def select_level(value):
    return f'Selected "{value}" orthology level'


celery_app = celery.Celery('main', broker='redis://redis/1', backend='redis://redis/1')


class DashProxy():
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

    def _enter(self, args):
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

    def _exit(self):
        res = tuple(
            self._outputs.get(k, no_update)
            for k in self._output_order
        )

        self._outputs.clear()
        self._data.clear()
        self.triggered.clear()

        return res

    @wraps(dash_app.callback)
    @classmethod
    def callback(cls, *args, **kwargs):
        def deco(func):
            dp = cls(args)
            def wrapper(*args2):
                dp._enter(args2)
                func(dp)
                return dp._exit()
            return dash_app.callback(*args, **kwargs)(wrapper)
        return deco

def decode_int(*items:bytes, default=0) -> int:
    if len(items)==1:
        return int(items[0]) if items[0] else default

    return map(
        lambda x: int(x) if x else default,
        items,
    )


def decode_str(*items, default=''):
    if len(items)==1:
        return items[0].decode() if items[0] else default

    return map(
        lambda x: x.decode() if x else default,
        items,
    )

def display_progress(status, total, current, msg):
    if status in ('Enqueued', 'Executing', 'Error'):
        pbar = {
            "style": {"height": "30px"}
        }
        if total < 0:
            # Special progress bar modes:
            # -1 unknown length style
            # -2 static message
            # -3 Waiting in the queue
            pbar['max'] = 100
            pbar['value'] = 100
            animate = total != -2 # not static message
            pbar['animated'] = animate
            pbar['striped'] = animate

            if total == -3:
                llid = decode_int(user.db.get("/queueinfo/last_launched_id")) + 1
                if current > llid:
                    msg = f"~{current - llid} tasks before yours"
                else:
                    msg = "almost running"
        else:
            # normal progressbar
            pbar['animated'] = False
            pbar['striped'] = False
            pbar['max'] = total
            pbar['value'] = current
            msg = f"{msg} ({current}/{total})"

        if status == 'Error':
            pbar['color'] = 'danger'
        else:
            pbar['color'] = 'info'

        return dbc.Row(
                dbc.Col(
                    dbc.Progress(
                        children=html.Span(
                            msg,
                            className="justify-content-center d-flex position-absolute w-100",
                            style={"color": "black"},
                        ),
                        **pbar,
                    ),
                    md=8, lg=6,
                ),
            justify='center')
    return None


@DashProxy.callback(
    Output('table-progress-updater', 'disabled'), # refresh_disabled

    Output('uniprotAC', 'value'),
    Output('dropdown', 'value'),
    Output('dropdown2', 'value'),

    Output('output_row', 'children'), # output

    Output('input_version', 'data'),
    Output('submit-button2', 'disabled'),

    Input('submit-button', 'n_clicks'),
    Input('table-progress-updater', 'n_intervals'),

    State('task_id', 'data'),
    State('input_version', 'data'),

    State('uniprotAC', 'value'),
    State('dropdown', 'value'),
    State('dropdown2', 'value'),

)
def table(dp:DashProxy):
    """Perform action (cancel/start building the table)"""
    task_id = dp['task_id', 'data']
    if ('submit-button', 'n_clicks') in dp.triggered:
        # Sending data
        with user.db.pipeline(transaction=True) as pipe:
            pipe.incr(f"/tasks/{task_id}/stage/table/version")
            pipe.execute_command("COPY", f"/tasks/{task_id}/stage/table/version", f"/tasks/{task_id}/stage/table/input_version", "REPLACE")
            pipe.mset({
                f"/tasks/{task_id}/request/proteins": dp['uniprotAC', 'value'],
                f"/tasks/{task_id}/request/dropdown1": dp['dropdown', 'value'],
                f"/tasks/{task_id}/request/dropdown2": dp['dropdown2', 'value'],
            })
            # Remove the data
            pipe.unlink(
                f"/tasks/{task_id}/stage/table/dash-table",
                f"/tasks/{task_id}/stage/table/message",
                f"/tasks/{task_id}/stage/table/missing_msg",
                f"/tasks/{task_id}/stage/table/status",
            )
            new_version = pipe.execute()[0]
            dp['input_version', 'data'] = new_version
        dp['submit-button2', 'disabled'] = True
        # enqueuing the task
        celery_app.signature(
            'tasks.build_table',
            args=(task_id, new_version)
        ).apply_async()

        # Trying to set status to enqueued if the task isn't already running
        with user.db.pipeline(transaction=True) as pipe:
            while True:
                try:
                    pipe.watch(f"/tasks/{task_id}/stage/table/status")
                    status = pipe.get(f"/tasks/{task_id}/stage/table/status")
                    if status is not None:
                        # Task has already modified it to something else, so we are not enqueued
                        break
                    # Task is still in the queue
                    pipe.multi()
                    pipe.mset({
                        f"/tasks/{task_id}/stage/table/status": 'Enqueued',
                        f"/tasks/{task_id}/stage/table/total": -3,
                    })
                    pipe.incr("/queueinfo/cur_id")
                    pipe.execute_command("COPY", "/queueinfo/cur_id", f"/tasks/{task_id}/stage/table/current", "REPLACE")
                    pipe.execute()
                    break
                except redis.WatchError:
                    continue

    # fill the output row
    # here because of go click, first launch or interval
    with user.db.pipeline(transaction=True) as pipe:
        while True:
            try:
                pipe.watch(f"/tasks/{task_id}/stage/table/input_version")
                input_version = pipe.get(f"/tasks/{task_id}/stage/table/input_version")
                input_version = decode_int(input_version)

                keys = [
                    f"/tasks/{task_id}/stage/table/status",
                    f"/tasks/{task_id}/stage/table/message",
                    f"/tasks/{task_id}/stage/table/current",
                    f"/tasks/{task_id}/stage/table/total",
                    f"/tasks/{task_id}/stage/table/missing_msg",
                    f"/tasks/{task_id}/stage/table/dash-table",
                ]
                if input_version > dp['input_version', 'data']:
                    # db has newer data, fetch it also
                    keys.extend((
                        f"/tasks/{task_id}/request/proteins",
                        f"/tasks/{task_id}/request/dropdown1",
                        f"/tasks/{task_id}/request/dropdown2",
                    ))
                pipe.multi()
                pipe.set(f"/tasks/{task_id}/accessed", int(time.time()))
                pipe.mget(*keys)
                exec_res = pipe.execute()[-1]
                status, msg, current, total, missing_msg, table_data, *extra = exec_res
                status, msg, missing_msg = decode_str(status, msg, missing_msg)
                current, total = decode_int(current, total)

                if extra:
                    proteins, dropdown, dropdown2 = decode_str(*extra)
                    if input_version:
                        dp['input_version', 'data'] = input_version
                    if proteins:
                        dp['uniprotAC', 'value'] = proteins
                    if dropdown:
                        dp['dropdown', 'value'] = dropdown
                    if dropdown2:
                        dp['dropdown2', 'value'] = dropdown2
                break
            except redis.WatchError:
                continue

    dp['table-progress-updater', 'disabled'] = (status not in ('Enqueued', 'Executing'))

    output = []
    if missing_msg:
        output.append(
            dbc.Row(
                dbc.Col(
                    dbc.Alert(
                        f"Unknown proteins: {missing_msg[:-2]}",
                        className="alert-warning",
                    ),
                    md=8, lg=6,
                ),
                justify='center',
            ),
        )

    progress_bar = display_progress(status, total, current, msg)
    if progress_bar is not None:
        output.append(progress_bar)

    if status == 'Done':
        data = json.loads(table_data)
        output.append(
            dbc.Row(dbc.Col(
                html.Div(
                    dash_table.DataTable(**data, filter_action="native"),
                    style={"overflow-x": "scroll"},
                    className="pb-3",
                ),
                md=12,
            ),
            justify='center',
        ))

    dp['submit-button2', 'disabled'] = status != 'Done'
    dp['output_row', 'children'] = html.Div(children=output)


# @DashProxy.callback(
#     Output('heatmap-progress-updater', 'disabled'),
#     Output('tree-progress-updater', 'disabled'),

#     Input('heatmap-progress-updater', 'n_intervals'),
#     Input('tree-progress-updater', 'n_intervals'),


#     Input('submit-button2', 'n_clicks'),
#     Input('submit-button2', 'disabled'),

#     State('dropdown2', 'value'),
#     State('task_id', 'data'),
# )
# def call(dp:DashProxy):
#     task_id = dp['task_id', 'data']
#     level = dp['dropdown2', 'value']
#     render_new = False
#     disable = False
#     if ('submit-button', 'n_clicks') in dp.triggered:
#         render_new = True
#         #start rendering
#         keys = [
#             f"/tasks/{task_id}/stage/table/status",
#             f"/tasks/{task_id}/stage/table/message",
#             f"/tasks/{task_id}/stage/table/current",
#             f"/tasks/{task_id}/stage/table/total",
#             f"/tasks/{task_id}/stage/table/missing_msg",
#             f"/tasks/{task_id}/stage/table/dash-table",
#         ]
#     if ('submit-button2', 'disabled') in dp.triggered:
#         disable = dp['submit-button2', 'disabled']

#     ...
#     output = []

#     if render_new or disable:
#          with user.db.pipeline(transaction=True) as pipe:
#             pipe.incr(f"/tasks/{task_id}/stage/heatmap/version")
#             pipe.incr(f"/tasks/{task_id}/stage/tree/version")
#             pipe.unlink(
#                 f"/tasks/{task_id}/stage/heatmap/status",
#                 f"/tasks/{task_id}/stage/tree/status",
#             )
#             res = pipe.execute()
#             heatmap_ver = res[0]
#             tree_ver = res[1]

#     if render_new:
#         pipe.set(f"/tasks/{task_id}/accessed", int(time.time()))
#         celery_app.signature(
#             'tasks.build_heatmap',
#             args=(task_id, heatmap_ver)
#         ).apply_async()
#         celery_app.signature(
#             'tasks.build_tree',
#             args=(task_id, heatmap_ver)
#         ).apply_async()

#         dp['heatmap-progress-updater', 'disabled'] = False
#         dp['tree-progress-updater', 'disabled'] = False

#     if ('heatmap-progress-updater', 'n_intervals') in dp.triggered:
#         with user.db.pipeline(transaction=True) as pipe:
#             pipe.mget(
#                 f"/tasks/{task_id}/stage/heatmap/status",
#                 f"/tasks/{task_id}/stage/heatmap/message",
#                 f"/tasks/{task_id}/stage/heatmap/current",
#                 f"/tasks/{task_id}/stage/heatmap/total",
#             )
#             status, message, current, total = pipe.execute()
#             current, total = decode_int(current, total)
#             status, message = decode_str(status, message)

#             progress_bar = display_progress(status, total, current, f"Heatmap: {message}")
#             if progress_bar:
#                 output.append(progress_bar)

#             if status == "Done":
#                 output.append(
#                     dbc.Row(
#                         dbc.Col(
#                             html.Img(
#                                 src=f'/files/{task_id}/Correlation.png?nocache={int(time.time())}',
#                                 id="corr",
#                             )
#                         ),
#                     ),
#                 )
#     if ('tree-progress-updater', 'n_intervals') in dp.triggered:
#         with user.db.pipeline(transaction=True) as pipe:
#             pipe.mget(
#                 f"/tasks/{task_id}/stage/tree/status",
#                 f"/tasks/{task_id}/stage/tree/message",
#                 f"/tasks/{task_id}/stage/tree/current",
#                 f"/tasks/{task_id}/stage/tree/total",
#             )
#             status, message, current, total = pipe.execute()
#             current, total = decode_int(current, total)
#             status, message = decode_str(status, message)

#             progress_bar = display_progress(status, total, current, f"Tree: {message}")
#             if progress_bar:
#                 output.append(progress_bar)
#             if status == "Done":
#                 output.append(
#                     dbc.Row(
#                         dbc.Col(
#                             PhydthreeComponent(
#                                 url=f'/files/{task_id}/{level}_cluser.xml?nocache={int(time.time())}'
#                             )
#                         ),
#                     ),
#                 )
#     dp['table-progress-updater', 'disabled'] = (status not in ('Enqueued', 'Executing'))


#     SPARQL_wrap(level)
#     corri = correlation_img(level)
#     pres_xml_url = presence_img(level)




@dash_app.server.route('/files/<task_id>/<name>')
def serve_user_file(task_id, name):
    uid = decode_str(user.db.get(f"/tasks/{task_id}/userid"))
    if flask.session.get("USER_ID", '') != uid:
        flask.abort(403)
    response = flask.make_response(flask.send_from_directory(user.path(), name))
    if name.lower().endswith(".xml"):
        response.mimetype = "text/xml"
    response.headers["Cache-Control"] = 'no-store, no-cache, must-revalidate, max-age=0'

    return response
