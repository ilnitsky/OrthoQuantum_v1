import os
import os.path
import time
import json
import secrets
import shutil
from contextlib import suppress

import urllib.parse as urlparse
from dash import Dash
from dash.dependencies import Input, Output, State
import dash_table
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import flask
from flask_compress import Compress
import redis

from phydthree_component import PhydthreeComponent

from . import layout
from . import user
from .utils import DashProxy, DashProxyCreator, GROUP, decode_int, PBState, DEBUG


app = flask.Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config["COMPRESS_REGISTER"] = False
app.config["COMPRESS_MIMETYPES"] = [
    'image/svg+xml',
    'text/html',
    'text/css',
    'text/xml',
    'application/json',
    'application/javascript'
]
compress = Compress()
compress.init_app(app)


DEMO_TID = os.environ["DEMO_TID"]
TAXID_CACHE = {}
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

        args = urlparse.parse_qs(url.query, keep_blank_values=True)
        task_id = args.get('task_id', (None,))[0]

        if 'create' not in args:
            # Attempt to fill in the task id
            if task_id is None or not get_task(task_id):
                # load last task
                last_task = user.db.lrange(f"/users/{flask.session['USER_ID']}/tasks", -1, -1)
                if last_task and get_task(last_task[0]):
                    task_id = last_task[0]
                else:
                    task_id = None

        if not task_id:
            # create task
            task_id = new_task()

        new_args = urlparse.urlencode({"task_id": task_id})
        search = f"?{new_args}"

        return layout.dashboard(task_id), search

    if pathname == '/prottree':
        args = urlparse.parse_qs(url.query, keep_blank_values=True)
        task_id = args.get('task_id', (None,))[0]
        prot_id = args.get('prot_id', (None,))[0]

        if task_id is None or prot_id is None or not get_task(task_id):
            return dcc.Location(pathname="/", id="some_id2", hash="1", refresh=True), search
        if '-' in prot_id:
            prot_ids = prot_id.split('-')
            prot_ids.sort()
            prot_id = prot_ids[0]
        did_schedule = False
        ignore_prottree_cache = True
        while True:
            try:
                with user.db.pipeline(transaction=True) as pipe:
                    pipe.watch(f"/prottree_tasks/{prot_id}/progress")
                    status = pipe.hget(f"/prottree_tasks/{prot_id}/progress", "status")
                    if ignore_prottree_cache or status in (None, "Error"):
                        pipe.multi()
                        pipe.xadd(
                            "/queues/prottree",
                            {
                                "prot_id": prot_id,
                            },
                        )
                        pipe.hset(f"/prottree_tasks/{prot_id}/progress",
                            mapping={
                                "status": 'Enqueued',
                                "message": "Gene/protein subfamily tree",
                            }
                        )
                        res = pipe.execute()
                        did_schedule = True
                break
            except Exception:
                continue
        if did_schedule:
            user.db.hset(f"/prottree_tasks/{prot_id}/progress", "q_id", res[0])
        return layout.prottree(prot_id), search
    if pathname == '/reports':
        return layout.reports, search
    if pathname == '/blast':
        return layout.blast, search
    return '404', search


# prottree page
@dash_proxy.callback(
    Output('prottree_progress_updater', 'disabled'),
    Output('prottree_container', 'children'),

    Input('prottree_progress_updater', 'n_intervals'),

    State('prot_id', 'data'),
)
def prottree(dp: DashProxy):
    prot_id = dp['prot_id', 'data']

    data = user.db.hgetall(f"/prottree_tasks/{prot_id}/progress")
    msg = data['message']
    if data['status'] == "Done":
        dp['prottree_progress_updater', 'disabled'] = True
        dp["prottree_container", "children"] = PhydthreeComponent(
            url=f'/prottree/{prot_id}.xml',
            height=2000,
            leafCount=142,
            version=0,
        )
        return

    pbar = {
        "style": {"height": "30px"},
        'color': 'info',
        'max': 100,
        'value': 100,
        'animated': True,
        'striped': True,
    }
    if data['status'] == "Enqueued":
        # show_q_pos
        gueue_len = user.get_queue_length(
            queue_key='/queues/prottree',
            worker_group_name=GROUP,
            task_q_id=data['q_id'],
        )

        if gueue_len > 0:
            msg = f"{msg}: {gueue_len} task{'s' if gueue_len>1 else ''} before yours"
        else:
            msg = f"{msg}: starting"
    elif data['status'] == "Error":
        dp['prottree_progress_updater', 'disabled'] = True
        pbar['color'] = 'danger'
        pbar['animated'] = False
        pbar['striped'] = False
    # elif data['status'] == "Executing":
        # Nothing to do, defaults are fine

    dp["prottree_container", "children"] = dbc.Progress(
        children=html.Span(
            msg,
            className="justify-content-center d-flex position-absolute w-100",
            style={"color": "black"},
            key="prottree_progress_text"
        ),
        key="prottree_progress_bar",
        **pbar,
    )


if DEBUG:
    @dash_app.callback(
        Output('flush-button', 'children'),
        Input('flush-button', 'n_clicks'),
    )
    def flush_db_cache(n):
        if not n:
            return "Flush Cache"
        user.db.xadd("/queues/flush_cache", {"n": n})
        return f"Flush Cache: {n}"



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

    with user.db.pipeline(transaction=True) as pipe:
        while True:
            try:
                pipe.watch(f"/users/{user_id}/task_counter")
                pipe.multi()
                pipe.incr(f"/users/{user_id}/task_counter")
                pipe.execute_command("COPY",f"/users/{user_id}/task_counter", f"/tasks/{task_id}/name", "REPLACE")
                pipe.rpush(f"/users/{user_id}/tasks", task_id)
                task_num = pipe.execute()[0]
                break
            except redis.WatchError:
                pass
        user.db.set(f"/tasks/{task_id}/name", f"Request #{task_num}")
    return task_id


def get_task(task_id):
    """Checks that task_id is valid and active, sets /accessed date to current"""
    if '/' in task_id:
        return False
    res = user.db.set(f"/tasks/{task_id}/accessed", int(time.time()), xx=(task_id != DEMO_TID))
    return res


# Show/hide request list dropdown
dash_app.clientside_callback(
    """
    function(n_clicks, cur_state) {
        if(n_clicks == null){
            // initial load
            return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        }

        if (cur_state){
            return ["dropdown-menu dropdown-menu-right", false];
        } else {
            return ["show dropdown-menu dropdown-menu-right", true];
        }
    }
    """,
    Output('request_list_dropdown', 'className'),
    Output('request_list_dropdown_shown', 'data'),
    Input("request_list_menu_item", "n_clicks"),
    State('request_list_dropdown_shown', 'data'),
)

@dash_proxy.callback(
    Output('request_list_dropdown', 'children'),

    Input('request_list_dropdown_shown', 'data'),
)
def request_list(dp: DashProxy):
    if dp.first_load:
        return
    res = [
        dbc.DropdownMenuItem(
            "New request",
            external_link=True, href=f"/?create",
        ),
        dbc.DropdownMenuItem(divider=True),
    ]
    if not dp['request_list_dropdown_shown', 'data']:
        # To show "loading" next time we are opened
        res.append(dbc.DropdownMenuItem("Loading...", disabled=True))
        dp['request_list_dropdown', 'children'] = res
        return

    user_id = flask.session.get("USER_ID")
    if not user_id:
        dp['request_list_dropdown', 'children'] = [
            dbc.DropdownMenuItem("New request"),
        ]
        return

    task_ids = user.db.lrange(f"/users/{user_id}/tasks", 0, -1)
    task_ids.reverse()

    stages = {
        'table': "Uniprot request",
        'vis': "Visualization",
        'tree': "Phylotree generation",
        'heatmap': "Heatmap generation",
        'blast': "Blast search",
    }
    with user.db.pipeline(transaction=False) as pipe:
        for task_id in task_ids:
            pipe.get(f"/tasks/{task_id}/name")
            for stage in stages:
                pipe.hget(f"/tasks/{task_id}/progress/{stage}", "status")
        data = pipe.execute()

    data_it = iter(data)
    for task_id in task_ids:
        name = next(data_it)

        not_started = True
        spinner = False
        message = None
        for stage, status in tuple(zip(stages, data_it)):
            # statuses: ("Enqueued", "Executing", "Waiting", "Done", "Error")
            if status == "Waiting":
                continue
            elif status is None:
                continue
            elif status == "Done":
                not_started = False
                continue
            elif status == "Enqueued":
                message = f"{stages[stage]} enqueued"
                spinner = True
            elif status == "Executing":
                message = f"{stages[stage]} in progress"
                spinner = True
            elif status == "Error":
                message = f"{stages[stage]} error"
            break
        else:
            if not_started:
                message = "No tasks were started"
            else:
                message = "All tasks are done"
        child_contents = [
            html.Strong(name),
            html.Br(),
        ]
        if spinner:
            child_contents.append(dbc.Spinner(
                size="sm",
                color="secondary",
                spinnerClassName="mr-2",
            ))
        child_contents.append(message)

        res.append(
            dbc.DropdownMenuItem(
                html.Div(child_contents),
                external_link=True, href=f"/?task_id={task_id}",
            )
        )

    dp['request_list_dropdown', 'children'] = res



@dash_proxy.callback(
    # TODO: add tooltips where needed and add them here
    # to enable hiding
    Output('tooltip-edit-title', 'className'),
    Output('tooltip-orthology', 'className'),
    Output('tooltip-gene-search', 'className'),
    Output('tooltip-blast-button', 'className'),
    Output('tooltip-table', 'className'),
    Output('tooltip-heatmap', 'className'),
    Output('tooltip-tree', 'className'),

    Input('tutorial_enabled', 'data'),
)
def tutorial_tooltips(dp: DashProxy):
    # Enable or disable all tooltips that are passed as outputs
    className = "" if dp['tutorial_enabled', 'data'] else "d-none"
    for el_id, el_property in dp._output_order:
        if el_property != 'className':
            continue
        dp[el_id, el_property] = className

dash_app.clientside_callback(
    """
    function(n_clicks, enabled) {
        if(n_clicks == null){
            // initial load
            return [enabled, enabled];
        }
        enabled=!enabled;
        return [enabled, enabled];
    }
    """,
    Output('tutorial_enabled', 'data'),
    Output('tutorial_checkbox', 'checked'),
    Input("tutorial-checkbox-div", "n_clicks"),
    State('tutorial_enabled', 'data'),
)


@dash_proxy.callback(
    Output('location-refresh-cont', 'children'),
    Input('demo-btn', 'n_clicks'),
)
def demo_data(dp: DashProxy):
    dp["location-refresh-cont", "children"] = None
    if not dp['demo-btn', 'n_clicks']:
        return

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



@dash_proxy.callback(
    Output('request-title', 'children'),
    Output('request-input', 'value'),
    Output('edit-request-title', 'className'),
    Output('request-input', 'className'),

    Input('edit-request-title', 'n_clicks'),
    Input('request-input', 'n_blur'),
    Input('request-input', 'n_submit'),

    State('request-input', 'value'),
    State('request-title', 'children'),
    State('task_id', 'data'),
)
def request_title(dp: DashProxy):
    task_id = dp['task_id', 'data']
    if dp.first_load:
        # set from db
        dp['request-title', 'children'] = user.db.get(f"/tasks/{task_id}/name")
    elif dp.triggered.intersection((('request-input', 'n_blur'), ('request-input', 'n_submit'))):
        # set in db, update and show the text
        dp['edit-request-title', 'className'] = "text-decoration-none"
        dp['request-input', 'className'] = "form-control-lg d-none"
        new_name = dp['request-input', 'value'].strip()
        if new_name:
            # Only if new name is not empty
            dp['request-title', 'children'] = new_name
            user.db.set(f"/tasks/{task_id}/name", new_name)
    else:
        # show editing interface
        dp['edit-request-title', 'className'] = "text-decoration-none d-none"
        dp['request-input', 'className'] = "form-control-lg"
        dp['request-input', 'value'] = dp['request-title', 'children']


@dash_proxy.callback(
    Output('taxid_input', 'options'),
    Output('taxid_input', 'value'),
    Output('taxid_input_numeric', 'data'),

    Input('taxid_input', 'search_value'),
    Input('tax-level-dropdown', 'value'),

    State('taxid_input_numeric', 'data'),
)
def taxid_options(dp: DashProxy):
    should_load_text = dp.first_load or ('tax-level-dropdown', 'value') in dp.triggered
    level_id = dp['tax-level-dropdown', 'value']
    if ('taxid_input', 'search_value') in dp.triggered:
        # if numeric - give user an option to input it
        # if clear or non-numeric - load text autocomplete if needed
        if search_val := dp['taxid_input', 'search_value'].strip():
            try:
                search_val = int(search_val)
            except Exception:
                if dp['taxid_input_numeric', 'data']:
                    dp['taxid_input_numeric', 'data'] = False
                    should_load_text = True
            else:
                dp["taxid_input", "options"] = TAXID_CACHE[level_id].copy()
                if not dp['taxid_input_numeric', 'data']:
                    dp['taxid_input_numeric', 'data'] = True
                dp["taxid_input", "options"].append({'label': dp['taxid_input', 'search_value'], 'value': search_val})


    if should_load_text and level_id:
        if level_id not in TAXID_CACHE:
            TAXID_CACHE[level_id] = json.loads(user.db.get(f"/availible_levels/{level_id}/search_dropdown"))

        dp["taxid_input", "options"] = TAXID_CACHE[level_id]

@dash_proxy.callback(
    Output('search-prot-button', 'children'),
    Output('search-prot-button', 'disabled'),
    Output('prot_search_updater', 'disabled'),
    Output('prot-codes', 'value'),
    Output('prot-search-result', 'data'),

    Input('search-prot-button', 'n_clicks'),
    Input('prot_search_updater', 'n_intervals'),

    State('taxid_input', 'value'),
    State('prot-codes', 'value'),
    State('search-prot-button', 'disabled'),
    State('task_id', 'data'),
    # State('taxid_input_numeric', 'data'),
)
def search_taxid(dp: DashProxy):
    if dp.first_load:
        return
    task_id = dp['task_id', 'data']
    if ('search-prot-button', 'n_clicks') in dp.triggered:
        prot_codes = dp['prot-codes', 'value'].strip()
        if prot_codes.startswith("#"):
            return
        if not dp['taxid_input', 'value']:
            #TODO: show error?
            return
        dp['prot_search_updater', 'disabled'] = False
        dp['search-prot-button', 'disabled'] = True
        dp['search-prot-button', 'children'] = [dbc.Spinner(size="sm", spinnerClassName="mr-2"), "Searching..."]
        with user.db.pipeline(transaction=False) as pipe:
            pipe.delete(f"/tasks/{task_id}/stage/prot_search/result")
            pipe.xadd(
                "/queues/seatch_prot",
                {
                    "task_id": task_id,
                    "prot_codes": prot_codes,
                    "taxid": dp['taxid_input', 'value']
                },
            )
            pipe.execute()
    elif ('prot_search_updater', 'n_intervals') in dp.triggered:
        res = user.db.get(f"/tasks/{task_id}/stage/prot_search/result")
        if res is not None:
            dp['prot_search_updater', 'disabled'] = True
            dp['search-prot-button', 'disabled'] = False
            dp['search-prot-button', 'children'] = "Find Uniprot ACs ➜"
            dp['prot-codes', 'value'] = ''
            dp['prot-search-result', 'data'] = res


dash_app.clientside_callback(
    """
    function(button_n_clicks, blast_value, cur_state) {
        if (dash_clientside.callback_context.triggered.length){
            trigger = dash_clientside.callback_context.triggered[0].prop_id;
            if (trigger == "blast-button.n_clicks"){
                cur_state = !cur_state;
            } else if (trigger == "blast-button-input-value.data") {
                cur_state = blast_value > 0
            }
        }
        if (cur_state){
            return ["Disable BLAST", true, false];
        } else {
            return ["Enable BLAST", false, true];
        }
    }
    """,
    Output("blast-button", "children"),
    Output("blast-options", "is_open"),
    Output("blast-button", "outline"),

    Input("blast-button", "n_clicks"),
    Input("blast-button-input-value", "data"),
    State("blast-options", "is_open"),
)

for name in ("pident", "qcovs"):
    dash_app.clientside_callback(
        """
        function(text_input_val, slider_val, data_input_val, blast_enabled) {
            noupd = window.dash_clientside.no_update;
            if (!blast_enabled){
                // blast is disabled, force-valid even if error
                // to allow sending the request
                return [false, noupd, noupd, noupd];
            }

            var val = NaN;
            var trigger = null;
            var no_update_field = null;

            if (dash_clientside.callback_context.triggered.length){
                trigger = dash_clientside.callback_context.triggered[0].prop_id;
            }
            switch(trigger){
                case "|NAME|-input.value":
                    val = text_input_val;
                    no_update_field = 1;
                    break;
                case "|NAME|-slider.value":
                    val = slider_val;
                    no_update_field = 2;
                    break;
                case "|NAME|-input-val.data":
                    val = data_input_val;
                    no_update_field = 3;
                    break;
                default:
                    // initial load
                    if (isNaN(data_input_val) || data_input_val<0 || data_input_val>100){
                        val = 70;
                    }else{
                        val = data_input_val;
                    }
                    break;
            }
            var text_val = val;
            val = Number(val);
            var invalid = false;
            if (isNaN(val)){
                invalid = true;
            }else{
                text_val = val;
                invalid = !((0 < val) && (val <= 100));
            }
            var output = [invalid, text_val, val, val];
            if (isNaN(val)){
                output[2] = noupd;
            }
            if (no_update_field != null){
                output[no_update_field] = noupd;
            }
            return output;
        }
        """.replace("|NAME|", name),
        Output(f"{name}-input", "invalid"),
        Output(f"{name}-input", "value"),
        Output(f"{name}-slider", "value"),
        Output(f"{name}-output-val", "data"),

        Input(f"{name}-input", "value"),
        Input(f"{name}-slider", "value"),
        Input(f"{name}-input-val", "data"),
        Input("blast-options", "is_open"),
    )



@dash_proxy.callback(
    Output('cancel-button', 'className'),
    Output('progress_updater', 'disabled'),
    Input('table_version', 'data'),
    Input('input1_version', 'data'),
    Input('table_version_target', 'data'),
    Input('tree_version_target', 'data'),

    Input('vis_version', 'data'),
    Input('heatmap_version', 'data'),
    Input('tree_version', 'data'),
    Input('blast_version', 'data'),

)
def progress_updater_running(dp: DashProxy):
    if dp.first_load:
        dp['progress_updater', 'disabled'] = True
        return
    versions = (
        'table_version',
        'vis_version',
        'heatmap_version',
        'tree_version',
        'blast_version',
    )
    if any(dp[key, 'data']< DO_NOT_REFRESH for key in versions):
        dp['progress_updater', 'disabled'] = False
        dp['cancel-button', 'className'] = "float-right"
    elif (dp['table_version_target', 'data'] > dp['table_version', 'data']) or \
        (dp['tree_version_target', 'data'] > dp['tree_version', 'data']):
        dp['progress_updater', 'disabled'] = False
        dp['cancel-button', 'className'] = "float-right d-none"
    else:
        dp['progress_updater', 'disabled'] = True
        dp['cancel-button', 'className'] = "float-right d-none"



dash_app.clientside_callback(
    """
    function(zoomVal) {
        zoomVal = Number(zoomVal);
        if (isNaN(zoomVal)){
            zoomVal = 100;
        }

        if (zoomVal>100){
            zoomVal = zoomVal*2 - 100;
        }
        zoomVal = (zoomVal/100).toFixed(2);

        return [
            zoomVal + "x",
            {
                transform: "scale("+zoomVal+")",
                transformOrigin: "0 0",
            },
        ]
    }
    """,
    # Output('request_list_dropdown', 'className'),
    Output('svg_zoom_text', 'children'),
    Output('ssr_tree_img', 'style'),
    Input("svg_zoom", "value"),
    # State('request_list_dropdown_shown', 'data'),
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

    Output('vis_progress_container', 'children'),
    Output('vis_version', 'data'),

    Output('heatmap_title_row', 'style'),
    Output('heatmap_progress_container', 'children'),
    Output('heatmap_version', 'data'),
    Output('heatmap_container', 'children'),
    Output("corr_table_container", "children"),

    Output('tree_title_row', 'style'),
    Output('tree_progress_container', 'children'),
    Output('tree_version', 'data'),
    Output('tree_container', 'children'),
    Output('ssr_tree_block', 'style'),
    Output('ssr_tree_img', 'src'),
    Output("show_groups", "checked"),
    Output("show_species", "checked"),

    Output('blast_version', 'data'),
    Output('blast_progress_container', 'children'),

    Output('input1_refresh', 'data'),

    Input('progress_updater', 'n_intervals'),

    State('input1_version', 'data'),

    State('table_version', 'data'),
    State('vis_version', 'data'),
    State('heatmap_version', 'data'),
    State('tree_version', 'data'),
    State('blast_version', 'data'),

    State('task_id', 'data'),
    State('input1_refresh', 'data'),
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
            f"/tasks/{task_id}/stage/tree/info",
            f"/tasks/{task_id}/stage/tree/opts",
        )
        res = pipe.execute()
    res_it = iter(res)
    info = dict(zip(stages, res_it))
    input1_version, tree_info, tree_opts = next(res_it)
    input1_version = decode_int(input1_version)
    if tree_info:
        tree_info = json.loads(tree_info)
    else:
        tree_info = None
    if tree_opts:
        tree_opts = json.loads(tree_opts)
    else:
        tree_opts = {}


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
                refresh_interval = min(refresh_interval, 2500)

        render_pbar = tgt_ver == DO_REFRESH
        if dp[f"{stage}_version", "data"] != tgt_ver:
            dp[f"{stage}_version", "data"] = tgt_ver
            if stage in VISUAL_COMPONENTS:
                show_component[stage] = data['status'] == 'Done'
            render_pbar = render_pbar or data['status'] == 'Error'
            if not render_pbar:
                dp[f"{stage}_progress_container", "children"] = None

        if render_pbar:
            if stage in ('tree', 'heatmap'):
                # show the title if rendering progress bars
                dp[f"{stage}_title_row", "style"] = {}
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
                # HACK: queue for SSR is called /ssr, but it uses stage name "tree"
                # There is no queue called "tree", since tree xml generation is a
                # subtask of the "vis" task (which has its own queue)
                if stage == "tree":
                    queue_key=f"/queues/ssr"
                else:
                    queue_key=f"/queues/{stage}"


                gueue_len = user.get_queue_length(
                    queue_key=queue_key,
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
                    key=f"{stage}_progress_text",
                ),
                key=f"{stage}_progress_bar",
                **pbar,
            )

    for stage, do_show in show_component.items():
        if not do_show:
            dp[f"{stage}_container", "children"] = None
            if stage == "heatmap":
                dp["corr_table_container", "children"] = None
                dp[f"{stage}_title_row", "style"] = {'display': 'none'}
            elif stage == "tree":
                dp[f"{stage}_title_row", "style"] = {'display': 'none'}
                dp["ssr_tree_block", "style"] = {"display": "none"}
                dp["ssr_tree_img", "src"] = ""

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
            dp[f"{stage}_title_row", "style"] = {}
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
                        page_size=20,
                    )
                else:
                    # table updated between requests, ensure to make a request soon
                    refresh_interval = min(refresh_interval, 300)
            except Exception:
                pass
        elif stage == 'tree':
            dp[f"{stage}_title_row", "style"] = {}
            dp["ssr_tree_block", "style"] = {"display": "none"}
            dp["ssr_tree_img", "src"] = ""
            tree_kind = tree_info['kind']
            if tree_kind == 'interactive':
                dp[f"{stage}_container", "children"] = PhydthreeComponent(
                    url=f'/files/{task_id}/tree.xml?nocache={version}',
                    height=2000,
                    leafCount=tree_info['shape'][0],
                    version=version,
                )
            else:
                assert tree_kind in ('svg', 'png')
                dp[f"{stage}_container", "children"] = None
                dp["ssr_tree_block", "style"] = {}
                dp["ssr_tree_img", "src"] = f"/files/{task_id}/ssr_img.{tree_kind}?version={version}"
                showNodesType = tree_opts.get("showNodesType", "only leaf")
                showNodeNames = tree_opts.get("showNodeNames", True)
                dp['show_groups', 'checked'] = showNodeNames and showNodesType != "only leaf"
                dp['show_species', 'checked'] = showNodeNames and showNodesType != "only inner"

    if input1_version > dp['input1_version', 'data']:
        # db has newer data, update output values
        dp['input1_refresh', 'data'] += 1

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
    Output("wrong-input-2", "is_open"),
    Output("blast-button-input-value", "data"),

    Output("pident-input-val", "data"),
    Output("qcovs-input-val", "data"),
    Output("evalue", "value"),

    ###
    Output('uniprotAC', 'value'),
    Output('tax-level-dropdown', 'value'),
    Output('input1_version', 'data'),
    Output('table_version_target', 'data'),
    Output('tree_version_target', 'data'),
    ###

    ###
    Input('submit-button', 'n_clicks'),
    Input('rerenderSSR_button', 'n_clicks'),
    Input('input1_refresh', 'data'),
    Input('cancel-button', 'n_clicks'),
    Input('prot-search-result', 'data'),
    ###

    State('task_id', 'data'),
    State("pident-input", "invalid"),
    State("qcovs-input", "invalid"),

    State("blast-options", "is_open"),
    State("blast-button-input-value", "data"),
    State("pident-output-val", "data"),
    State("qcovs-output-val", "data"),

    State("show_groups", "checked"),
    State("show_species", "checked"),

    State("evalue", "value"),
    State("submit-button", "children"),

    ###
    State('input1_version', 'data'),
    State('uniprotAC', 'value'),
    State('tax-level-dropdown', 'value'),
    ###
)
def submit(dp:DashProxy):
    task_id = dp['task_id', 'data']

    if ('submit-button', 'n_clicks') in dp.triggered:
        # button press triggered
        if dp["blast-options", "is_open"]:
            if dp["pident-input", "invalid"] or dp["qcovs-input", "invalid"]:
                # client validation failed
                dp["wrong-input-2", "is_open"] = True
                return
            # performing server validation
            try:
                pident = float(dp["pident-output-val", "data"])
                qcovs = float(dp["qcovs-output-val", "data"])
                evalue = dp["evalue", "value"]
                if evalue not in ('-5', '-6', '-7', '-8'):
                    raise ValueError()
            except Exception:
                # client validation succeeded, server validation failed
                dp["wrong-input-2", "is_open"] = True
                return

            # validation succeeded
            dp["wrong-input-2", "is_open"] = False
        else:
            # no blast options, set to default ('') for redis request
            qcovs = ''
            pident = ''
            evalue = ''


        with user.db.pipeline(transaction=True) as pipe:
            user.enqueue(
                version_key=f"/tasks/{task_id}/stage/table/version",
                queue_key='/queues/table',
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
            user.cancel(
                version_key=f"/tasks/{task_id}/stage/tree/version",
                queue_key="/queues/ssr",
                queue_id_dest=f"/tasks/{task_id}/progress/tree",
                queue_hash_key="q_id",

                redis_client=pipe,
            )
            pipe.delete(
                f"/tasks/{task_id}/stage/table/missing_msg",
                f"/tasks/{task_id}/progress/heatmap",
                f"/tasks/{task_id}/progress/tree",
            )

            pipe.mset({
                f"/tasks/{task_id}/request/proteins": dp['uniprotAC', 'value'],
                f"/tasks/{task_id}/request/tax-level": dp['tax-level-dropdown', 'value'],

                f"/tasks/{task_id}/request/blast_enable": "1" if dp["blast-options", "is_open"] else "",
                f"/tasks/{task_id}/request/blast_evalue": evalue,
                f"/tasks/{task_id}/request/blast_pident": pident,
                f"/tasks/{task_id}/request/blast_qcovs": qcovs,

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
        dp['table_version_target', 'data'] = dp['input1_version', 'data']

    elif ('rerenderSSR_button', 'n_clicks') in dp.triggered:
        showGroups = dp['show_groups', 'checked']
        showSpecies = dp['show_species', 'checked']
        opts = {}
        if showGroups and showSpecies:
            opts["showNodesType"] = "all"
        elif showGroups:
            opts["showNodesType"] = "only inner"
        else:
            opts["showNodesType"] = "only leaf"
        opts["showNodeNames"] = showGroups or showSpecies

        with user.db.pipeline(transaction=True) as pipe:
            user.enqueue(
                version_key=f"/tasks/{task_id}/stage/tree/version",
                queue_key="/queues/ssr",
                queue_id_dest=f"/tasks/{task_id}/progress/tree",
                queue_hash_key="q_id",
                redis_client=pipe,

                task_id=task_id,
                stage="tree",
            )
            pipe.set(
                f"/tasks/{task_id}/stage/tree/opts",
                json.dumps(opts),
            )
            pipe.hset(f"/tasks/{task_id}/progress/tree",
                mapping={
                    "status": 'Enqueued',
                    'total': PBState.UNKNOWN_LEN,
                    "message": "Rerendering",
                }
            )
            res = pipe.execute()
        dp['tree_version_target', 'data'] = decode_int(res[0][0])

    elif ('input1_refresh', 'data') in dp.triggered or dp.first_load:
        # Server has newer data than we have, update dropdown value
        data = user.db.mget(
            f"/tasks/{task_id}/request/proteins",
            f"/tasks/{task_id}/request/tax-level",

            f"/tasks/{task_id}/request/blast_enable",
            f"/tasks/{task_id}/request/blast_evalue",
            f"/tasks/{task_id}/request/blast_pident",
            f"/tasks/{task_id}/request/blast_qcovs",

            f"/tasks/{task_id}/stage/table/input_version"
        )
        if not any(data):
            return
        (
            dp['uniprotAC', 'value'],
            dp['tax-level-dropdown', 'value'],

            blast_enable,
            evalue,
            pident,
            qcovs,

            input1_version,
        ) = data
        if evalue:
            dp["evalue", "value"] = evalue
        if pident:
            with suppress(ValueError):
                dp["pident-input-val", "data"] = float(pident)
        if qcovs:
            with suppress(ValueError):
                dp["qcovs-input-val", "data"] = float(qcovs)

        dp['input1_version', 'data'] = decode_int(input1_version)

        dp["blast-button-input-value", "data"] = abs(dp["blast-button-input-value", "data"]) + 1
        if not blast_enable:
            dp["blast-button-input-value", "data"] *= -1
    elif ('cancel-button', 'n_clicks') in dp.triggered:
        with user.db.pipeline(transaction=True) as pipe:
            user.cancel(
                version_key=f"/tasks/{task_id}/stage/table/version",
                queue_key='/queues/table',
                queue_id_dest=f"/tasks/{task_id}/progress/table",
                queue_hash_key="q_id",

                redis_client=pipe,
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
            user.cancel(
                version_key=f"/tasks/{task_id}/stage/tree/version",
                queue_key="/queues/ssr",
                queue_id_dest=f"/tasks/{task_id}/progress/tree",
                queue_hash_key="q_id",

                redis_client=pipe,
            )
            pipe.delete(
                f"/tasks/{task_id}/progress/heatmap",
                f"/tasks/{task_id}/progress/tree",
            )

            res = pipe.execute()

            dp['table_version_target', 'data'] = 0  # stop updator
            dp['tree_version_target', 'data'] = 0  # stop updator
    elif ('prot-search-result', 'data') in dp.triggered:
        cur_val = dp['uniprotAC', 'value'].strip()
        if cur_val:
            dp['uniprotAC', 'value'] = f"{cur_val}\n\n{dp['prot-search-result', 'data']}"
        else:
            dp['uniprotAC', 'value'] = dp['prot-search-result', 'data']


@dash_app.server.route('/files/<task_id>/<name>')
@compress.compressed()
def serve_user_file(task_id, name):
    # uid = user.db.get(f"/tasks/{task_id}/user_id")
    # if flask.session.get("USER_ID", '') != uid:
    #     flask.abort(403)
    response = flask.make_response(flask.send_from_directory(f"/app/user_data/{task_id}", name))
    if name.lower().endswith(".xml"):
        response.mimetype = "text/xml"
    elif name.lower().endswith(".svg"):
        response.mimetype = "image/svg+xml"
    return response


@dash_app.server.route('/prottree/<name>')
@compress.compressed()
def serve_prottree(name):
    response = flask.make_response(flask.send_from_directory(f"/app/user_data/prottrees", name))
    if name.lower().endswith(".xml"):
        response.mimetype = "text/xml"
    elif name.lower().endswith(".svg"):
        response.mimetype = "image/svg+xml"
    return response



@dash_app.server.route('/some_non_public_ssr_path')
def serve_ssr():
    return flask.send_file(f"/app/ssr/index.html")
