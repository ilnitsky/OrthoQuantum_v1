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
import flask

from phydthree_component import PhydthreeComponent

from . import layout
from . import user
from .utils import DashProxy, _DashProxy, GROUP, decode_int


app = flask.Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

# external JavaScript files
external_scripts = [
    {
        'src': 'https://code.jquery.com/jquery-2.2.4.min.js',
        'integrity': 'sha256-BbhdlvQf/xTY9gja0Dq3HiwQF8LaCRTXxZKRutelT44=',
        'crossorigin': 'anonymous'
    },
    {
        'src': 'https://d3js.org/d3.v3.min.js',
        # 'integrity': 'sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa',
        # 'crossorigin': 'anonymous'
    },
]
# external CSS stylesheets
external_stylesheets = [
    dbc.themes.UNITED,
]

dash_app = Dash(__name__, server=app, suppress_callback_exceptions=True, external_scripts=external_scripts, external_stylesheets=external_stylesheets)
dash_app.layout = layout.index

dash_proxy = DashProxy(dash_app)

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
    search = ''
    if url.query:
        search = f'?{url.query}'

    if pathname == '':
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
            new_args = urlparse.urlencode(args)
            if new_args:
                search = f"?{urlparse.urlencode(args)}"

        return layout.dashboard(args['task_id']), search
    if pathname == '/reports':
        return layout.reports, search
    if pathname == '/blast':
        return layout.blast, search
    if pathname == '/flush_cache':
        user.db.xadd("/queues/flush_cache", {"t":"t"})
        return 'flushing', search

    return '404', search

@dash_proxy.callback(
    Output("blast-button", "children"),
    Output("blast-options", "is_open"),
    Output("blast-button", "outline"),

    Input("blast-button", "n_clicks"),
    Input("blast-button-input-value", "data"),
    State("blast-options", "is_open"),
)
def toggle_collapse(dp:_DashProxy):
    if ("blast-button", "n_clicks") in dp.triggered:
        dp["blast-options", "is_open"] = not dp["blast-options", "is_open"]
    elif ("blast-button-input-value", "data") in dp.triggered:
        dp["blast-options", "is_open"] = dp["blast-button-input-value", "data"]>0

    if dp["blast-options", "is_open"]:
        dp["blast-button", "children"] = "Disable BLAST"
        dp["blast-button", "outline"] = False
    else:
        dp["blast-button", "children"] = "Enable BLAST"
        dp["blast-button", "outline"] = True

@dash_proxy.callback(
    Output("pident-input", "invalid"),
    Output("pident-input", "value"),
    Output("pident-slider", "value"),
    Output("pident-output-val", "data"),

    Input("pident-input", "value"),
    Input("pident-slider", "value"),
    Input("pident-input-val", "data"),
)
def pident_val(dp:_DashProxy):
    if dp.first_load or ("pident-input-val", "data") in dp.triggered:
        val = dp["pident-input-val", "data"]
        dp["pident-input", "invalid"] = False
        dp["pident-input", "value"] = val
        dp["pident-slider", "value"] = val
    elif ("pident-input", "value") in dp.triggered:
        try:
            val = float(dp["pident-input", "value"].replace(' ', '').replace(',', '.'))
            dp["pident-slider", "value"] = val
        except Exception:
            val = 0
    elif ("pident-slider", "value") in dp.triggered:
        val = dp["pident-slider", "value"]
        dp["pident-input", "value"] = val


    dp["pident-input", "invalid"] = not(0 < val <= 100)
    dp["pident-output-val", "data"] = 0 if dp["pident-input", "invalid"] else val





# TODO: need this?
@dash_app.callback(Output('dd-output-container', 'children'), [Input('dropdown', 'value')])
def select_level(value):
    return f'Selected "{value}" orthology level'


def display_progress(queue, status, total, current, msg):
    print(queue, status, total, current, msg)
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
            gueue_len = user.get_queue_length(
                queue_key=queue,
                worker_group_name=GROUP,
                current=current
            )

            if gueue_len > 0:
                msg = f"{gueue_len} task{'s' if gueue_len>1 else ''} before yours"
            else:
                msg = "running"


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


@dash_proxy.callback(
    Output('table-progress-updater', 'disabled'), # refresh_disabled

    Output('uniprotAC', 'value'),
    Output('dropdown', 'value'),

    Output('output_row', 'children'), # output

    Output('input_version', 'data'),
    Output('submit-button2', 'disabled'),

    Input('submit-button', 'n_clicks'),
    Input('table-progress-updater', 'n_intervals'),

    State('task_id', 'data'),
    State('input_version', 'data'),

    State('uniprotAC', 'value'),
    State('dropdown', 'value'),
)
def table(dp:DashProxy):
    """Perform action (cancel/start building the table)"""
    task_id = dp['task_id', 'data']
    queue = "/queues/table"

    if ('submit-button', 'n_clicks') in dp.triggered:
        # Sending data
        with user.db.pipeline(transaction=True) as pipe:
            user.enqueue(
                version_key=f"/tasks/{task_id}/stage/table/version",
                queue_key=queue,
                queue_id_dest=f"/tasks/{task_id}/stage/table/current",
                redis_client=pipe,

                task_id=task_id,
                stage="table",
            )
            pipe.mset({
                f"/tasks/{task_id}/request/proteins": dp['uniprotAC', 'value'],
                f"/tasks/{task_id}/request/dropdown1": dp['dropdown', 'value'],

                f"/tasks/{task_id}/stage/table/status": 'Enqueued',
                f"/tasks/{task_id}/stage/table/total": -3,
            })
            pipe.execute_command(
                "COPY",
                f"/tasks/{task_id}/stage/table/version",
                f"/tasks/{task_id}/stage/table/input_version",
                "REPLACE",
            )

            # Remove the data
            pipe.unlink(
                f"/tasks/{task_id}/stage/table/dash-table",
                f"/tasks/{task_id}/stage/table/message",
                f"/tasks/{task_id}/stage/table/missing_msg",
                f"/tasks/{task_id}/stage/vis/status",
            )
            new_version = pipe.execute()[0][0]
        dp['input_version', 'data'] = new_version
        dp['submit-button2', 'disabled'] = True

    # fill the output row
    # here because of go click, first launch or interval

    status, msg, current, total, missing_msg, table_data, input_version = user.db.mget(
        f"/tasks/{task_id}/stage/table/status",
        f"/tasks/{task_id}/stage/table/message",
        f"/tasks/{task_id}/stage/table/current",
        f"/tasks/{task_id}/stage/table/total",
        f"/tasks/{task_id}/stage/table/missing_msg",
        f"/tasks/{task_id}/stage/table/dash-table",
        f"/tasks/{task_id}/stage/table/input_version",
    )

    total, input_version = decode_int(total, input_version)

    if input_version > dp['input_version', 'data']:
        # db has newer data, fetch it
        proteins, dropdown, input_version = user.db.mget(
            f"/tasks/{task_id}/request/proteins",
            f"/tasks/{task_id}/request/dropdown1",
            f"/tasks/{task_id}/stage/table/input_version"
        )
        input_version = decode_int(input_version)

        dp['input_version', 'data'] = input_version
        dp['uniprotAC', 'value'] = proteins
        dp['dropdown', 'value'] = dropdown

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

    if status in ('Enqueued', 'Executing', 'Error'):
        output.append(display_progress(queue, status, total, current, msg))
    elif status == 'Done':
        data = json.loads(table_data)
        output.append(
            dbc.Row(dbc.Col(
                html.Div(
                    dash_table.DataTable(**data, filter_action="native", page_size=40),
                    className="pb-3",
                ),
                md=12,
            ),
            justify='center',
        ))

    dp['submit-button2', 'disabled'] = status != 'Done'
    dp['table-progress-updater', 'disabled'] = (status not in ('Enqueued', 'Executing'))
    dp['output_row', 'children'] = html.Div(children=output)


@dash_proxy.callback(
    Output('vis-output-container', 'children'),
    Output('dropdown2', 'value'),
    Output('input2-version', 'data'),
    Output('progress-updater-2', 'disabled'),
    Output("wrong-input-2", "is_open"),
    Output("blast-button-input-value", "data"),
    Output("pident-input-val", "data"),
    Output("evalue", "value"),

    Input('submit-button2', 'n_clicks'),
    Input('submit-button2', 'disabled'),
    Input('progress-updater-2', 'n_intervals'),

    State('task_id', 'data'),
    State('dropdown2', 'value'),
    State('input2-version', 'data'),
    State("pident-input", "invalid"),
    State("blast-options", "is_open"),
    State("evalue", "value"),
    State("pident-output-val", "data"),
    State("blast-button-input-value", "data"),
)
def start_vis(dp:DashProxy):
    task_id = dp['task_id', 'data']
    queue = "/queues/vis"

    if ('submit-button2', 'disabled') in dp.triggered:
        if dp['submit-button2', 'disabled']:
            # First stage data was changed, clear the current data
            dp['vis-output-container', 'children'] = None
            # Stop running tasks
            user.db.incr(f"/tasks/{task_id}/stage/vis/version")
            return

    if ('submit-button2', 'n_clicks') in dp.triggered:
        if dp['submit-button2', 'disabled']:
            # button was pressed in disabled state??
            return
        # button press triggered
        if dp["blast-options", "is_open"] and dp["pident-input", "invalid"]:
            dp["wrong-input-2", "is_open"] = True
            return
        dp["wrong-input-2", "is_open"] = False

        with user.db.pipeline(transaction=True) as pipe:
            user.enqueue(
                version_key=f"/tasks/{task_id}/stage/vis/version",
                queue_key=queue,
                queue_id_dest=f"/tasks/{task_id}/stage/vis/current",
                redis_client=pipe,

                task_id=task_id,
                stage="vis",
            )

            pipe.mset({
                f"/tasks/{task_id}/stage/vis/status": "Enqueued",
                f"/tasks/{task_id}/stage/vis/total": -3,
                f"/tasks/{task_id}/request/dropdown2": dp['dropdown2', 'value'],
                f"/tasks/{task_id}/request/blast_enable": "1" if dp["blast-options", "is_open"] else "",
                f"/tasks/{task_id}/request/blast_evalue": dp["evalue", "value"],
                f"/tasks/{task_id}/request/blast_pident": dp["pident-output-val", "data"],
                f"/tasks/{task_id}/stage/vis/heatmap-message": "",
                f"/tasks/{task_id}/stage/vis/tree-message": "",
            })
            pipe.execute_command(
                "COPY",
                f"/tasks/{task_id}/stage/vis/version",
                f"/tasks/{task_id}/stage/vis/input2-version",
                "REPLACE",
            )
            vis_ver = pipe.execute()[0][0]
        dp['input2-version', 'data'] = vis_ver

    # fill the output row
    # here because of "go" click, first launch or interval refresh
    version, status, msg, current, total, input_version, heatmap_msg, tree_msg, tree_leaf_count = user.db.mget(
        f"/tasks/{task_id}/stage/vis/version",
        f"/tasks/{task_id}/stage/vis/status",
        f"/tasks/{task_id}/stage/vis/message",
        f"/tasks/{task_id}/stage/vis/current",
        f"/tasks/{task_id}/stage/vis/total",
        f"/tasks/{task_id}/stage/vis/input2-version",
        f"/tasks/{task_id}/stage/vis/heatmap-message",
        f"/tasks/{task_id}/stage/vis/tree-message",
        f"/tasks/{task_id}/stage/vis/tree-res",
    )
    version, total, input_version, tree_leaf_count = decode_int(version, total, input_version, tree_leaf_count)

    if input_version > dp['input2-version', 'data']:
        # Server has newer data than we have, update dropdown value
        input_val, input_version, blast_enable, blast_evalue, blast_pident = user.db.mget(
            f"/tasks/{task_id}/request/dropdown2",
            f"/tasks/{task_id}/stage/vis/input2-version",
            f"/tasks/{task_id}/request/blast_enable",
            f"/tasks/{task_id}/request/blast_evalue",
            f"/tasks/{task_id}/request/blast_pident",
        )
        dp["blast-button-input-value", "data"] = abs(dp["blast-button-input-value", "data"]) + 1
        if not blast_enable:
            dp["blast-button-input-value", "data"] *= -1
        dp["evalue", "value"] = blast_evalue
        dp["pident-input-val", "data"] = blast_pident

        dp['input2-version', 'data'] = decode_int(input_version)
        dp['dropdown2', 'value'] = input_val

    dp['progress-updater-2', 'disabled'] = status not in ('Enqueued', 'Executing', 'Waiting')

    if status in ('Enqueued', 'Executing', 'Error'):
        dp[f'vis-output-container', 'children'] = display_progress(queue, status, total, current, msg)
    elif status in ('Waiting', 'Done'):
        if heatmap_msg == "Done":
            heatmap = dbc.Row(
                dbc.Col(
                    html.A(
                        html.Img(
                            src=f'/files/{task_id}/Correlation_preview.png?version={version}',
                            style={
                                'width': '100%',
                                'max-width': '1100px',
                            },
                            className="mx-auto",
                        ),
                        href=f'/files/{task_id}/Correlation.png?version={version}',
                        target="_blank",
                        className="mx-auto",
                    ),
                    className="text-center",
                ),
                className="mx-4",
            )
        elif heatmap_msg.startswith("Error"):
            heatmap = display_progress(queue, "Error", -2, 0, heatmap_msg)
        else:
            heatmap = display_progress(queue, "Executing", -1, 0, heatmap_msg)

        if tree_msg == "Done":
            tree = dbc.Row(
                dbc.Col(
                    PhydthreeComponent(
                        url=f'/files/{task_id}/cluser.xml?nocache={version}',
                        height=2000,
                        leafCount=tree_leaf_count,
                    ),
                    className="mx-5 mt-3",
                )
            )
        elif tree_msg.startswith("Error"):
            tree = display_progress(queue, "Error", -2, 0, tree_msg)
        else:
            tree = display_progress(queue, "Executing", -1, 0, tree_msg)
        dp[f'vis-output-container', 'children'] = [
            heatmap,
            tree
        ]


@dash_app.server.route('/files/<task_id>/<name>')
def serve_user_file(task_id, name):
    # uid = user.db.get(f"/tasks/{task_id}/user_id")
    # if flask.session.get("USER_ID", '') != uid:
    #     flask.abort(403)
    response = flask.make_response(flask.send_from_directory(f"/app/user_data/{task_id}", name))
    if name.lower().endswith(".xml"):
        response.mimetype = "text/xml"

    return response
