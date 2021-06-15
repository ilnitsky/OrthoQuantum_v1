import os
import os.path
import time
import json
import secrets
import shutil

import urllib.parse as urlparse
from dash import Dash
from dash.dependencies import Input, Output, State
import dash_table
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import flask

from phydthree_component import PhydthreeComponent

from . import layout
from . import user
from .utils import DashProxy, DashProxyCreator, GROUP, decode_int, PBState, DEBUG


app = flask.Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
DEMO_TID = os.environ["DEMO_TID"]
# app.debug = DEBUG

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
title = "OrthoQuantum"
dash_app = Dash(
    __name__,
    server=app, suppress_callback_exceptions=True,
    external_scripts=external_scripts, external_stylesheets=external_stylesheets,
    title=title,
    update_title=("⟳ " + title) if DEBUG else (title + "..."),
)
# dash_app.enable_dev_tools(
#     debug=True,
#     dev_tools_ui=True,
#     dev_tools_serve_dev_bundles=True,
#     dev_tools_silence_routes_logging=False,
# )
dash_app.layout = layout.index

dash_proxy = DashProxyCreator(dash_app)

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
    user.db.incr(f"/users/{user_id}/task_counter")
    # user.db.set(f"/tasks/{task_id}/name", f"Request {task_no}")

    # Publishes the task to the system, must be the last action
    user.db.rpush(f"/users/{user_id}/tasks", task_id)

    return task_id


def get_task(task_id):
    """Checks that task_id is valid and active, sets /accessed date to current"""
    if '/' in task_id:
        return False
    if task_id == DEMO_TID:
        user.db.set(f"/tasks/{task_id}/accessed", int(time.time()))
        return True
    res = user.db.set(f"/tasks/{task_id}/accessed", int(time.time()), xx=True)
    return res




@dash_proxy.callback(
    Output('location-refresh-cont', 'children'),
    Input('demo-btn', 'n_clicks'),
)
def demo(dp: DashProxy):
    dp["location-refresh-cont", "children"] = None
    if not dp['demo-btn', 'n_clicks']:
        return
    print(dp.first_load, dp.triggered, dp['demo-btn', 'n_clicks'])
    new_task_id = new_task()
    src_path = user.DATA_PATH/DEMO_TID
    if not src_path.exists():
        print(f"Create demo by visiting task_id {DEMO_TID}")
        return
    shutil.copytree(user.DATA_PATH/DEMO_TID, user.DATA_PATH/new_task_id)
    base = f"/tasks/{DEMO_TID}"
    tgt = f"/tasks/{new_task_id}"
    with user.db.pipeline(transaction=False) as pipe:
        for item in user.db.scan_iter(match=f"{base}/*"):
            pipe.execute_command(
                "COPY", item, tgt+item[len(base):], "REPLACE"
            )
        pipe.execute()

    dp["location-refresh-cont", "children"] = dcc.Location(
        id='location-refresh',
        refresh=True,
        search=f"?task_id={new_task_id}"
    )







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

    return '404', search

if DEBUG:
    @dash_app.callback(
        Output('flush-button', 'children'),
        Input('flush-button', 'n_clicks'),
    )
    def flush(n):
        if not n:
            return "Flush Cache"
        user.db.xadd("/queues/flush_cache", {"n": n})
        return f"Flush Cache: {n}"


@dash_proxy.callback(
    Output('progress_updater', 'disabled'),
    Input('table_version', 'data'),
    Input('input1_version', 'data'),
    Input('input2_version', 'data'),
    Input('vis_version', 'data'),
    Input('heatmap_version', 'data'),
    Input('tree_version', 'data'),
    Input('blast_version', 'data'),

)
def progress_updater_running(dp: DashProxy):
    if dp.first_load:
        dp['progress_updater', 'disabled'] = True
        return
    dp['progress_updater', 'disabled'] = not (
        dp['table_version', 'data'] < DO_NOT_REFRESH or
        dp['vis_version', 'data'] < DO_NOT_REFRESH or
        dp['heatmap_version', 'data'] < DO_NOT_REFRESH or
        dp['tree_version', 'data'] < DO_NOT_REFRESH or
        dp['blast_version', 'data'] < DO_NOT_REFRESH or
        dp['input1_version', 'data'] > dp['table_version', 'data'] or
        dp['input2_version', 'data'] > dp['vis_version', 'data']
    )

DO_REFRESH_NO_PROGRESS = -2
DO_REFRESH = -1
DO_NOT_REFRESH = 0
VISUAL_COMPONENTS = {'table', 'heatmap', 'tree'}

@dash_proxy.callback(
    Output('progress_updater', 'interval'),

    Output('table_progress_container', 'children'),
    Output('table_version', 'data'),
    Output('table_container', 'children'),
    Output('missing_prot_alert', 'is_open'),
    Output('missing_prot_alert', 'children'),
    Output('submit-button2', 'disabled'),

    Output('vis_progress_container', 'children'),
    Output('vis_version', 'data'),

    Output('heatmap_progress_container', 'children'),
    Output('heatmap_version', 'data'),
    Output('heatmap_container', 'children'),
    Output("corr_table_container", "children"),

    Output('tree_progress_container', 'children'),
    Output('tree_version', 'data'),
    Output('tree_container', 'children'),

    Output('blast_version', 'data'),
    Output('blast_progress_container', 'children'),

    Output('input1_refresh', 'data'),
    Output('input2_refresh', 'data'),

    Input('progress_updater', 'n_intervals'),

    State('input1_version', 'data'),
    State('input2_version', 'data'),

    State('table_version', 'data'),
    State('vis_version', 'data'),
    State('heatmap_version', 'data'),
    State('tree_version', 'data'),
    State('blast_version', 'data'),

    State('task_id', 'data'),
    State('input1_refresh', 'data'),
    State('input2_refresh', 'data'),
)
def progress_updater(dp: DashProxy):
    task_id = dp['task_id', 'data']
    stages = ('table', 'vis', 'tree', 'heatmap', 'blast')

    show_component = {}

    with user.db.pipeline(transaction=True) as pipe:
        for stage in stages:
            pipe.hgetall(f"/tasks/{task_id}/progress/{stage}")
        pipe.mget(
            f"/tasks/{task_id}/stage/table/input_version",
            f"/tasks/{task_id}/stage/vis/input2-version",
            f"/tasks/{task_id}/stage/tree/leaf_count",
        )
        res = pipe.execute()
    res_it = iter(res)
    info = dict(zip(stages, res_it))
    input1_version, input2_version, tree_leaf_count = decode_int(*next(res_it))

    refresh_interval = float('+inf')

    for stage, data in info.items():
        data: dict
        print(stage, data)
        data.setdefault('status', None)

        if data['status'] is None or data['status'] == "Error":
            tgt_ver = DO_NOT_REFRESH
        elif data['status'] == "Done":
            tgt_ver = int(data['version'])
        else:
            tgt_ver = DO_REFRESH_NO_PROGRESS if data['status'] == 'Waiting' else DO_REFRESH
            if data['status'] == 'Waiting' or stage == 'blast':
                refresh_interval = min(refresh_interval, 5000)
            else:
                refresh_interval = min(refresh_interval, 500)

        render_pbar = tgt_ver == DO_REFRESH
        if dp[f"{stage}_version", "data"] != tgt_ver:
            dp[f"{stage}_version", "data"] = tgt_ver
            if stage in VISUAL_COMPONENTS:
                show_component[stage] = data['status'] == 'Done'
            render_pbar = render_pbar or data['status'] == 'Error'
            if not render_pbar:
                dp[f"{stage}_progress_container", "children"] = None

        if render_pbar:
            pbar = {
                "style": {"height": "30px"},
                'color': 'danger' if data['status'] == "Error" else 'info'
            }
            data['total'] = decode_int(data['total'])
            msg = data['message']
            if data['total'] < 0:
                pbar['max'] = 100
                pbar['value'] = 100
                animate = data['total'] != -2 # not static message
                pbar['animated'] = animate
                pbar['striped'] = animate
            else:
                data['current'] = decode_int(data['current'])
                pbar['max'] = data['total']
                pbar['value'] = data['current']
                pbar['animated'] = False
                pbar['striped'] = False
                msg = f"{msg} ({data['current']}/{data['total']})"

            if data['status'] == 'Enqueued':
                gueue_len = user.get_queue_length(
                    queue_key=f"/queues/{stage}",
                    worker_group_name=GROUP,
                    task_q_id=data['q_id'],
                )

                if gueue_len > 0:
                    msg = f"{msg}: {gueue_len} task{'s' if gueue_len>1 else ''} before yours"
                else:
                    msg = f"{msg}: starting"
            dp[f"{stage}_progress_container", "children"] = dbc.Progress(
                children=html.Span(
                    msg,
                    className="justify-content-center d-flex position-absolute w-100",
                    style={"color": "black"},
                ),
                **pbar,
            )

    req = {}

    for stage, do_show in show_component.items():
        if not do_show:
            dp[f"{stage}_container", "children"] = None
            if stage == "heatmap":
                dp[f"corr_table_container", "children"] = None
            continue
        version = dp[f"{stage}_version", "data"]
        if stage == 'table':
            dp[f"table_container", "children"] = None
            try:
                with open(user.DATA_PATH/task_id/"Info_table.json", "r") as f:
                    tbl_data = json.load(f)

                if tbl_data['version'] == version:
                    dp[f"table_container", "children"] = dash_table.DataTable(
                        **tbl_data['data'],
                        filter_action="native",
                        page_size=40,
                    )
                else:
                    # table updated between requests, ensure to make a request soon
                    refresh_interval = min(refresh_interval, 300)
            except Exception:
                pass

        elif stage == 'heatmap':
            dp[f"{stage}_container", "children"] = html.A(
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
            )

            dp["corr_table_container", "children"] = None
            try:
                with open(user.DATA_PATH/task_id/"Correlation_table.json", "r") as f:
                    tbl_data = json.load(f)

                if tbl_data['version'] == version:
                    dp["corr_table_container", "children"] = dash_table.DataTable(
                        **tbl_data['data'],
                        filter_action="native",
                        page_size=40,
                    )
                else:
                    # table updated between requests, ensure to make a request soon
                    refresh_interval = min(refresh_interval, 300)
            except Exception:
                pass



        elif stage == 'tree':
            print(f"writing tree {version}")
            dp[f"{stage}_container", "children"] = PhydthreeComponent(
                url=f'/files/{task_id}/tree.xml?nocache={version}',
                height=2000,
                leafCount=tree_leaf_count,
                version=version,
            )


    if 'table' in show_component:
        dp['submit-button2', 'disabled'] = info['table'].get('status') != 'Done'

    if input1_version > dp['input1_version', 'data']:
        # db has newer data, update output values
        dp['input1_refresh', 'data'] += 1

    if input2_version > dp['input2_version', 'data']:
        # db has newer data, update output values
        dp['input2_refresh', 'data'] += 1

    if info['table'].get('status') == 'Executing' or 'table' in show_component:
        missing_prot_msg = user.db.get(f"/tasks/{task_id}/stage/table/missing_msg")
        dp['missing_prot_alert', 'is_open'] = bool(missing_prot_msg)
        if dp['missing_prot_alert', 'is_open']:
            dp['missing_prot_alert', 'children'] = f"Unknown proteins: {missing_prot_msg[:-2]}"
        else:
            # table updated between requests, ensure to make a request soon
            refresh_interval = min(refresh_interval, 300)


    if refresh_interval != float('+inf'):
        dp['progress_updater', 'interval'] = refresh_interval


@dash_proxy.callback(
    Output('uniprotAC', 'value'),
    Output('dropdown', 'value'),

    Output('input1_version', 'data'),

    Input('submit-button', 'n_clicks'),
    Input('input1_refresh', 'data'),

    State('task_id', 'data'),
    State('input1_version', 'data'),

    State('uniprotAC', 'value'),
    State('dropdown', 'value'),
)
def table(dp:DashProxy):
    """Perform action (cancel/start building the table)"""
    task_id = dp['task_id', 'data']
    queue = "/queues/table"

    if ('submit-button', 'n_clicks') in dp.triggered:
        with user.db.pipeline(transaction=True) as pipe:
            user.enqueue(
                version_key=f"/tasks/{task_id}/stage/table/version",
                queue_key=queue,
                queue_id_dest=f"/tasks/{task_id}/progress/table",
                queue_hash_key="q_id",
                redis_client=pipe,

                task_id=task_id,
                stage="table",
            )
            user.cancel(
                version_key=f"/tasks/{task_id}/stage/vis/version",
                queue_key="/queues/vis",
                queue_id_dest=f"/tasks/{task_id}/progress/vis",
                queue_hash_key="q_id",

                redis_client=pipe,
            )
            user.cancel(
                version_key=f"/tasks/{task_id}/stage/blast/version",
                queue_key="/queues/blast",
                queue_id_dest=f"/tasks/{task_id}/progress/blast",
                queue_hash_key="q_id",

                redis_client=pipe,
            )
            pipe.delete(
                f"/tasks/{task_id}/stage/table/dash-table",
                f"/tasks/{task_id}/stage/table/missing_msg",

                f"/tasks/{task_id}/progress/heatmap",
                f"/tasks/{task_id}/progress/tree",
            )

            pipe.mset({
                f"/tasks/{task_id}/request/proteins": dp['uniprotAC', 'value'],
                f"/tasks/{task_id}/request/dropdown1": dp['dropdown', 'value'],
            })
            pipe.hset(f"/tasks/{task_id}/progress/table",
                mapping={
                    "status": 'Enqueued',
                    'total': PBState.UNKNOWN_LEN,
                    "message": "Building table",
                }
            )
            pipe.execute_command(
                "COPY",
                f"/tasks/{task_id}/stage/table/version",
                f"/tasks/{task_id}/stage/table/input_version",
                "REPLACE",
            )
            res = pipe.execute()

        dp['input1_version', 'data'] = decode_int(res[0][0])
    elif ('input1_refresh', 'data') in dp.triggered or dp.first_load:
        data = user.db.mget(
            f"/tasks/{task_id}/request/proteins",
            f"/tasks/{task_id}/request/dropdown1",
            f"/tasks/{task_id}/stage/table/input_version"
        )
        if not any(data):
            return
        (
            dp['uniprotAC', 'value'],
            dp['dropdown', 'value'],
            input1_version,
        ) = data
        dp['input1_version', 'data'] = decode_int(input1_version)



@dash_proxy.callback(
    Output("blast-button", "children"),
    Output("blast-options", "is_open"),
    Output("blast-button", "outline"),

    Input("blast-button", "n_clicks"),
    Input("blast-button-input-value", "data"),
    State("blast-options", "is_open"),
)
def toggle_collapse(dp:DashProxy):
    if ("blast-button", "n_clicks") in dp.triggered:
        dp["blast-options", "is_open"] = not dp["blast-options", "is_open"]
    elif ("blast-button-input-value", "data") in dp.triggered:
        dp["blast-options", "is_open"] = dp["blast-button-input-value", "data"]>0

    dp["blast-button", "children"] = "Disable BLAST" if dp["blast-options", "is_open"] else "Enable BLAST"
    dp["blast-button", "outline"] = not dp["blast-options", "is_open"]


for name in ("pident", "qcovs"):
    @dash_proxy.callback(
        Output(f"{name}-input", "invalid"),
        Output(f"{name}-input", "value"),
        Output(f"{name}-slider", "value"),
        Output(f"{name}-output-val", "data"),

        Input(f"{name}-input", "value"),
        Input(f"{name}-slider", "value"),
        Input(f"{name}-input-val", "data"),
    )
    def slider_val(dp:DashProxy, name=name):
        if dp.first_load or (f"{name}-input-val", "data") in dp.triggered:
            val = float(dp[f"{name}-input-val", "data"])
            dp[f"{name}-input", "invalid"] = False
            dp[f"{name}-input", "value"] = val
            dp[f"{name}-slider", "value"] = val
        elif (f"{name}-input", "value") in dp.triggered:
            try:
                val = float(dp[f"{name}-input", "value"].replace(' ', '').replace(',', '.'))
                dp[f"{name}-slider", "value"] = val
            except Exception:
                val = 0
        elif (f"{name}-slider", "value") in dp.triggered:
            val = float(dp[f"{name}-slider", "value"])
            dp[f"{name}-input", "value"] = val


        dp[f"{name}-input", "invalid"] = not(0 < val <= 100)
        dp[f"{name}-output-val", "data"] = 0 if dp[f"{name}-input", "invalid"] else val



@dash_proxy.callback(
    Output('input2_version', 'data'),

    Output("wrong-input-2", "is_open"),
    Output("blast-button-input-value", "data"),

    Output("pident-input-val", "data"),
    Output("qcovs-input-val", "data"),
    Output("evalue", "value"),
    Output('dropdown2', 'value'),

    Input('submit-button2', 'n_clicks'),
    Input('input2_refresh', 'data'),

    State('task_id', 'data'),
    State('dropdown2', 'value'),
    State('input2_version', 'data'),
    State("pident-input", "invalid"),
    State("qcovs-input", "invalid"),

    State("blast-options", "is_open"),
    State("blast-button-input-value", "data"),
    State("pident-output-val", "data"),
    State("qcovs-output-val", "data"),

    State("evalue", "value"),
)
def start_vis(dp:DashProxy):
    task_id = dp['task_id', 'data']
    queue = "/queues/vis"

    if ('submit-button2', 'n_clicks') in dp.triggered:
        # button press triggered
        try:
            pident = float(dp["pident-output-val", "data"])
        except Exception:
            pident = None
        try:
            qcovs = float(dp["qcovs-output-val", "data"])
        except Exception:
            qcovs = None
        if dp["evalue", "value"] in ('-5', '-6', '-7', '-8'):
            evalue = dp["evalue", "value"]
        else:
            evalue = None

        if (
            (
                dp["blast-options", "is_open"] and (
                    dp["pident-input", "invalid"] or
                    dp["qcovs-input", "invalid"]
                )
            ) or
            pident is None or
            evalue is None
            ):
            dp["wrong-input-2", "is_open"] = True
            return

        dp["wrong-input-2", "is_open"] = False

        with user.db.pipeline(transaction=True) as pipe:
            user.enqueue(
                version_key=f"/tasks/{task_id}/stage/vis/version",
                queue_key=queue,
                queue_id_dest=f"/tasks/{task_id}/progress/vis",
                queue_hash_key="q_id",

                redis_client=pipe,

                task_id=task_id,
                stage="vis",
            )
            user.cancel(
                version_key=f"/tasks/{task_id}/stage/blast/version",
                queue_key="/queues/blast",
                queue_id_dest=f"/tasks/{task_id}/progress/blast",
                queue_hash_key="q_id",

                redis_client=pipe,
            )
            pipe.delete(
                f"/tasks/{task_id}/progress/heatmap",
                f"/tasks/{task_id}/progress/tree",
            )
            # Cancel possibly-running blast tasks
            pipe.incr(f"/tasks/{task_id}/stage/blast/version")

            pipe.mset({
                f"/tasks/{task_id}/request/dropdown2": dp['dropdown2', 'value'],
                f"/tasks/{task_id}/request/blast_enable": "1" if dp["blast-options", "is_open"] else "",
                f"/tasks/{task_id}/request/blast_evalue": evalue,
                f"/tasks/{task_id}/request/blast_pident": pident,
                f"/tasks/{task_id}/request/blast_qcovs": qcovs,

            })
            pipe.hset(f"/tasks/{task_id}/progress/vis",
                mapping={
                    "status": 'Enqueued',
                    'total': PBState.UNKNOWN_LEN,
                    "message": "Building visualization",
                }
            )
            pipe.execute_command(
                "COPY",
                f"/tasks/{task_id}/stage/vis/version",
                f"/tasks/{task_id}/stage/vis/input2_version",
                "REPLACE",
            )
            res = pipe.execute()
        dp['input2_version', 'data'] = decode_int(res[0][0])
    elif ('input2_refresh', 'data') in dp.triggered or dp.first_load:
        # Server has newer data than we have, update dropdown value
        data = user.db.mget(
            f"/tasks/{task_id}/stage/vis/input2-version",
            f"/tasks/{task_id}/request/blast_enable",
            f"/tasks/{task_id}/request/dropdown2",
            f"/tasks/{task_id}/request/blast_evalue",
            f"/tasks/{task_id}/request/blast_pident",
            f"/tasks/{task_id}/request/blast_qcovs",
        )
        if not any(data):
            return
        input2_version, blast_enable, dp['dropdown2', 'value'], dp["evalue", "value"], pident, qcovs = data
        dp["pident-input-val", "data"] = float(pident)
        dp["qcovs-input-val", "data"] = float(qcovs)

        dp["blast-button-input-value", "data"] = abs(dp["blast-button-input-value", "data"]) + 1
        if not blast_enable:
            print("blast-button-input-value")
            dp["blast-button-input-value", "data"] *= -1

        dp['input2_version', 'data'] = decode_int(input2_version)


@dash_app.server.route('/files/<task_id>/<name>')
def serve_user_file(task_id, name):
    # uid = user.db.get(f"/tasks/{task_id}/user_id")
    # if flask.session.get("USER_ID", '') != uid:
    #     flask.abort(403)
    response = flask.make_response(flask.send_from_directory(f"/app/user_data/{task_id}", name))
    if name.lower().endswith(".xml"):
        response.mimetype = "text/xml"

    return response
