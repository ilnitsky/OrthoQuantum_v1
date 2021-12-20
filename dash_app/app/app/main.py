from functools import partial
import os
import os.path
import time
import json
import secrets
import shutil
import redis
import math
import pandas as pd

import urllib.parse as urlparse
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import flask
from flask_compress import Compress

from . import layout
from . import user
from .utils import DashProxy, DashProxyCreator, decode_int, DEBUG, clamp, parse_int, parse_float


app = flask.Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config["COMPRESS_REGISTER"] = False
app.config["COMPRESS_MIMETYPES"] = [
    'image/svg+xml',
    'text/html',
    'text/csv',
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

dash_app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks == null){
            return window.dash_clientside.no_update;
        }
        return true;
    }
    """,
    Output('cookie_consent_given', 'data'),
    Input("accept_cookies_btn", "n_clicks"),
)


@dash_proxy.callback(
    Output('page-content', 'children'),
    Output('location', 'search'),
    Output('cookies_consent_modal', 'is_open'),
    Input('location', 'href'),
    Input('cookie_consent_given', 'data'),
)
def router_page(dp: DashProxy):
    href = dp['location', 'href']
    url = urlparse.urlparse(href)
    pathname = url.path.rstrip('/')

    if url.query:
        dp['location', 'search'] = f'?{url.query}'
    else:
        dp['location', 'search'] = ''

    if not dp['cookie_consent_given', 'data']:
        dp['cookies_consent_modal', 'is_open'] = True
        dp['page-content', 'children'] = None
        return
    dp['cookies_consent_modal', 'is_open'] = False

    if pathname == '':
        if not user.is_logged_in():
            dp['page-content', 'children'] = login(pathname)
            return

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
        dp['location', 'search'] = f"?{new_args}"

        dp['page-content', 'children'] = layout.dashboard(task_id)
        return

    if pathname == '/prottree':
        args = urlparse.parse_qs(url.query, keep_blank_values=True)
        task_id = args.get('task_id', (None,))[0]
        prot_id = args.get('prot_id', (None,))[0]

        if task_id is None or prot_id is None or not get_task(task_id):
            dp['page-content', 'children'] = dcc.Location(pathname="/", id="some_id2", hash="1", refresh=True)
            return
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
        dp['page-content', 'children'] = layout.prottree(prot_id)
        return
    if pathname == '/about':
        dp['page-content', 'children'] = layout.about(dash_app)
        return
    dp['page-content', 'children'] = "Page Not Found"


dash_app.clientside_callback(
    """
    function(trig_1, trig_2, n) {
        if (n == null){
            return window.dash_clientside.no_update;
        }
        if((trig_1 == n)||(trig_2 == n)){
            document.getElementById("csvdownload_done_link").click();
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('csvdownload_done_link', 'children'),
    Input('trigger_csv_download', 'data'),
    Input('trigger_csv_download_2', 'data'),
    State('tree_component', 'csv_render_n'),
)

@dash_proxy.callback(
    Output('trigger_csv_download_2', 'data'),
    Output('trigger_csv_download_refresh', 'data'),

    Input('tree_component', 'csv_render_n'),

    State('connection_id', 'data'),
    State('task_id', 'data'),
)
def csvdownload(dp: DashProxy):
    if dp.first_load:
        return
    task_id = dp['task_id', 'data']
    while True:
        try:
            with user.db.pipeline(transaction=True) as pipe:
                pipe.watch(f"/tasks/{task_id}/state")
                tree_ver, tree_blast_ver, tree_csv_ver = pipe.hmget(
                    f"/tasks/{task_id}/state",
                    "tree_version", "tree_blast_ver", "tree_csv_ver",
                )
                if not tree_ver:
                    raise RuntimeError("no tree_ver")
                tree_blast_ver = tree_blast_ver or '0'
                tree_csv_ver = tree_csv_ver or ''

                pipe.multi()
                if f'{tree_ver}_{tree_blast_ver}' > tree_csv_ver:
                    user.enqueue(
                        task_id, "tree_csv",
                        tgt_connection_id=dp['connection_id', 'data'],
                        csv_render_n=dp['tree_component', 'csv_render_n'],
                        redis_client=pipe,
                    )
                    pipe.execute()
                    dp['trigger_csv_download_refresh', 'data'] = dp['tree_component', 'csv_render_n']
                else:
                    dp['trigger_csv_download_2', 'data'] = dp['tree_component', 'csv_render_n']
                    return
            break
        except redis.WatchError:
            pass

# prottree page
@dash_proxy.callback(
    Output('prottree_progress_updater', 'disabled'),
    Output('prottree_progress_bar_container', 'children'),
    Output('prottree_tree', 'version'),

    Input('prottree_progress_updater', 'n_intervals'),

    State('prot_id', 'data'),
)
def prottree(dp: DashProxy):
    prot_id = dp['prot_id', 'data']

    data = user.db.hgetall(f"/prottree_tasks/{prot_id}/progress")
    msg = data['message']
    if data['status'] == "Done":
        dp['prottree_progress_updater', 'disabled'] = True
        dp['prottree_tree', 'version'] = data['version']
        dp["prottree_progress_bar_container", "children"] = None
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
        gueue_len = user.get_queue_pos(
            queue_key='/queues/prottree',
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

    dp["prottree_progress_bar_container", "children"] = dbc.Progress(
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
        pipe.incr(f"/users/{user_id}/task_counter")
        pipe.rpush(f"/users/{user_id}/tasks", task_id)
        user.update(task_id, title="New query", redis_pipe=pipe)
        task_num = pipe.execute()[0]
    user.update(task_id, title=f"Query #{task_num}")
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
            pipe.hget(f"/tasks/{task_id}/state", "title")
            pipe.hgetall(f"/tasks/{task_id}/enqueued")
            pipe.hgetall(f"/tasks/{task_id}/running")
        data = pipe.execute()

    data_it = iter(data)
    for task_id in task_ids:
        name = next(data_it)
        enqueued:dict = next(data_it)
        running:dict = next(data_it)

        for stage in stages:
            if stage in enqueued:
                message = f"{stages[stage]} enqueued"
                spinner = True
                break
            elif stage in running:
                message = f"{stages[stage]} in progress"
                spinner = True
                break
        else:
            message = "Ready"
            spinner = False

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
    Input('request_title_update', 'data'),

    State('request-input', 'value'),
    State('connection_id', 'data'),
    State('request-title', 'children'),
    State('task_id', 'data'),
)
def request_title(dp: DashProxy):
    if dp.first_load:
        return
    if dp.is_triggered_by(('request_title_update', 'data')):
        # set from db
        if dp['request-title', 'children'] != dp['request_title_update', 'data']:
            dp['request-title', 'children'] = dp['request_title_update', 'data']
    elif dp.is_triggered_by(('request-input', 'n_blur'), ('request-input', 'n_submit')):
        # set in db, update and show the text
        dp['edit-request-title', 'className'] = "text-decoration-none"
        dp['request-input', 'className'] = "form-control-lg d-none"
        new_name = dp['request-input', 'value'].strip()
        if new_name:
            # Only if new name is not empty
            dp['request-title', 'children'] = new_name
            user.update(
                dp['task_id', 'data'],
                dp['connection_id', 'data'],
                title=new_name
            )

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
    should_load_text = dp.first_load or dp.is_triggered_by(('tax-level-dropdown', 'value'))
    level_id = dp['tax-level-dropdown', 'value']
    if dp.is_triggered_by(('taxid_input', 'search_value')):
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

def filter_comments(data:str, only_first=False):
    res = []
    lines = data.split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if only_first:
            return '\n'.join(lines[i:])
        res.append(line)
    return '\n'.join(res)

@dash_proxy.callback(
    Output('search-prot-button', 'children'),
    Output('search-prot-button', 'disabled'),
    Output('prot-codes', 'value'),

    Input('search-prot-button', 'n_clicks'),
    Input('prot-search-result', 'data'),

    State('taxid_input', 'value'),
    State('prot-codes', 'value'),
    State('task_id', 'data'),)
def search_taxid(dp: DashProxy):
    if dp.first_load:
        return
    task_id = dp['task_id', 'data']
    if dp.is_triggered_by(('search-prot-button', 'n_clicks')):

        prot_codes = filter_comments(dp['prot-codes', 'value'])
        if not dp['taxid_input', 'value']:
            dp['prot-codes', 'value'] = f"# Error: organism was not selected\n{filter_comments(dp['prot-codes', 'value'], only_first=True)}"
            return
        if not prot_codes:
            dp['prot-codes', 'value'] = '# Error: no gene names entered'
            return

        dp['search-prot-button', 'disabled'] = True
        dp['search-prot-button', 'children'] = [dbc.Spinner(size="sm", spinnerClassName="mr-2"), "Searching..."]
        user.enqueue(
            task_id, "seatch_prot",
            prot_codes=prot_codes,
            taxid=dp['taxid_input', 'value'],
        )

    elif dp.is_triggered_by(('prot-search-result', 'data')):
        dp['search-prot-button', 'disabled'] = False
        dp['search-prot-button', 'children'] = "Find Uniprot ACs ➜"
        dp['prot-codes', 'value'] = ''

dash_app.clientside_callback(
    """
    function(n, is_open) {
        if (dash_clientside.callback_context.triggered.length!=0){
            return !is_open;
        }
        return false;
    }
    """,

    Output("corr_table_options_collapse", "is_open"),
    Input("corr_table_options_show", "n_clicks"),
    State("corr_table_options_collapse", "is_open"),
)


@dash_proxy.callback(
    Output("corr_table", "data"),
    Output('corr_table', 'columns'),

    Output('page_size', 'value'),
    Output('curr_page', 'value'),
    Output('min_quantile', 'value'),
    Output('max_quantile', 'value'),
    Output('min_corr', 'value'),
    Output('max_corr', 'value'),

    Output('total_pages', 'children'),

    ###
    Input("heatmap_container", "style"), # Update on show/hide

    Input('reset_corr_settings', 'n_clicks'),
    Input('curr_page_decr', 'n_clicks'),
    Input('curr_page_incr', 'n_clicks'),

    Input('curr_page', 'value'),
    Input('page_size', 'value'),
    Input('min_quantile', 'value'),
    Input('max_quantile', 'value'),
    Input('min_corr', 'value'),
    Input('max_corr', 'value'),

    State('task_id', 'data'),

)
def render_corr_table(dp:DashProxy):
    if dp["heatmap_container", "style"] != layout.SHOW:
        return
    task_id = dp['task_id', 'data']
    try:
        tbl = pd.read_pickle(user.DATA_PATH/task_id/"Correlation_table.pkl")
        tbl: pd.DataFrame
    except Exception:
        __import__("traceback").print_exc()
        dp["corr_table", "data"] = None
        dp["corr_table", "columns"] = None
        return

    if dp.is_triggered_by(('reset_corr_settings', 'n_clicks')):
        dp['curr_page', 'value'] = ''
        dp['page_size', 'value'] = ''
        dp['min_quantile', 'value'] = ''
        dp['max_quantile', 'value'] = ''
        dp['min_corr', 'value'] = ''
        dp['max_corr', 'value'] = ''


    min_quantile = clamp(0., parse_float(dp["min_quantile", "value"], 0.), 1.)
    max_quantile = clamp(0., parse_float(dp["max_quantile", "value"], 1.), 1.)

    min_corr = clamp(-1., parse_float(dp["min_corr", "value"], -1.), 1.)
    max_corr = clamp(-1., parse_float(dp["max_corr", "value"], 1.), 1.)

    tbl = tbl.loc[
        tbl["Corr"].between(min_corr, max_corr) &
        tbl["Quantile"].between(min_quantile, max_quantile)
    ]


    page_size = clamp(5, parse_int(dp['page_size', 'value'], 20), 100)

    page_count = math.ceil(tbl.shape[0]/page_size)

    curr_page = parse_int(dp['curr_page', 'value'], 1)

    if dp.is_triggered_by(('curr_page_decr', 'n_clicks')):
        curr_page -= 1
    elif dp.is_triggered_by(('curr_page_incr', 'n_clicks')):
        curr_page += 1

    if page_count == 0:
        curr_page = 0
    else:
        curr_page = clamp(1, curr_page, page_count)

    dp['page_size', 'value'] = page_size
    dp['curr_page', 'value'] = curr_page
    dp['min_quantile', 'value'] = min_quantile
    dp['max_quantile', 'value'] = max_quantile
    dp['min_corr', 'value'] = min_corr
    dp['max_corr', 'value'] = max_corr

    dp['total_pages', 'children'] = f"/{page_count}"

    if curr_page:
        tbl = tbl.iloc[(curr_page-1)*page_size:curr_page*page_size]

        dp["corr_table", "data"] = tbl.to_dict('records')
        dp["corr_table", "columns"] = [
            {
                "name": i,
                "id": i,
            }
            for i in tbl.columns
        ]
    else:
        dp["corr_table", "data"] = None
        dp["corr_table", "columns"] = None


dash_app.clientside_callback(
    """
    function(button_n_clicks, blast_value, cur_state) {
        if (dash_clientside.callback_context.triggered.length){
            trigger = dash_clientside.callback_context.triggered[0].prop_id;
            if (trigger == "blast-button.n_clicks"){
                cur_state = !cur_state;
            } else if (trigger == "blast-button-input-value.data") {
                cur_state = blast_value
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
    Output('svg_zoom_text', 'children'),
    Output('ssr_tree_img', 'style'),
    Input("svg_zoom", "value"),
)

#region Update processing
DB_2_DASH = {}
DB_2_DASH_KEYS = set()

def add_processor(func=None, /, **from_to):
    if not func:
        return partial(add_processor, **from_to)
    for k, v in from_to.items():
        if isinstance(v[0], str):
            v = (v,)
        DB_2_DASH[k] = (v, func)
        DB_2_DASH_KEYS.add(k)
    return func



_no_val = object()
def _basic_assign(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
    for dash_key in dash_keys:
        dp[dash_key] = upd[db_key]
def simple_processor(func=None, default=_no_val, exceptions=(Exception)):
    if func:
        if default is not _no_val:
            def assign(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
                for dash_key in dash_keys:
                    try:
                        dp[dash_key] = func(upd[db_key])
                    except exceptions:
                        dp[dash_key] = default
        else:
            def assign(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
                for dash_key in dash_keys:
                    dp[dash_key] = func(upd[db_key])
    else:
        assign = _basic_assign
    return assign


add_processor(
    simple_processor(),
    # db_key = dash_key,
    input_proteins = ('uniprotAC_update', 'data'),
    prot_search_result = ('prot-search-result', 'data'),
)

add_processor(
    simple_processor(str.strip),

    title = ('request_title_update', 'data'),
    input_tax_level = ('tax-level-dropdown', 'value'),
)

add_processor(
    simple_processor(bool),

    input_blast_enabled = ('blast-button-input-value', 'data')
)

def float_preserve_str(val:str):
    val = val.strip()
    _ = float(val)
    return val

add_processor(
    simple_processor(func=float_preserve_str, default="1e-5"),

    input_blast_evalue=("evalue", "value")
)


add_processor(
    simple_processor(func=float, default=70.0),

    input_blast_pident=("pident-input-val", "data"),
    input_blast_qcovs=("qcovs-input-val", "data"),
)


add_processor(
    simple_processor(func=lambda x: max(int(x), 5), default=600),

    input_max_proteins=("max-proteins", "value"),
)

@add_processor(
    missing_prots = (
        ('missing_prot_alert', 'children'),
        ('missing_prot_alert', 'is_open'),
    )
)
def missing_prot(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
    # TODO: move missing_prot_alert into state hash
    missing_prot_msg = upd.get(db_key)
    if missing_prot_msg:
        dp['missing_prot_alert', 'children'] = f"Unknown proteins: {missing_prot_msg}"
        dp['missing_prot_alert', 'is_open'] = True
    else:
        dp['missing_prot_alert', 'children'] = None
        dp['missing_prot_alert', 'is_open'] = False


@add_processor(
    table = (
        ('data_table', 'data'),
        ('data_table', 'columns'),
        ('table_container', 'style'),
    ),
)
def table(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
    if not upd[db_key]:
        # empty string in update - hide table
        dp['table_container', 'style'] = layout.HIDE
        return
    try:
        with open(user.DATA_PATH/dp['task_id', 'data']/"Info_table.json", "r") as f:
            tbl_data = json.load(f)
        for k, v in dash_keys:
            if k != 'data_table':
                continue
            dp[k, v] = tbl_data[v]
        dp['table_container', 'style'] = layout.SHOW

    except Exception:
        # TODO: report exception
        __import__("traceback").print_exc()
        pass

@add_processor(
    heatmap = (
        ("heatmap_img", "src"),
        ("heatmap_link", "href"),
        ("heatmap_container", "style"),
    ),
)
def heatmap(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
    task_id = dp['task_id', 'data']
    heatmap_version = upd[db_key]

    dp["heatmap_img", "src"] = f'/files/{task_id}/Correlation_preview.png?version={heatmap_version}'
    dp["heatmap_link", "href"] = f'/files/{task_id}/Correlation.png?version={heatmap_version}'

    dp["heatmap_container", "style"] = layout.SHOW


@add_processor(
    tree = (
        ('tree_header', 'style'),
        ("ssr_tree_block", "style"),

        ('tree_component', 'version'),
        ('tree_component', 'leafCount'),
        ("ssr_tree_img", "src"),
    ),
)
def tree(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
    task_id = dp['task_id', 'data']
    tree_info = upd[db_key]
    dp['tree_header', 'style'] = layout.SHOW

    kind = tree_info['kind']
    version = f"{upd['tree_version']}_{upd.get('tree_blast_ver', 0)}"
    shape = tree_info['shape']

    if kind == 'interactive':
        dp["ssr_tree_img", "src"] = ""
        dp["ssr_tree_block", "style"] = layout.HIDE
        dp["tree_component", "version"] = version
        dp["tree_component", "leafCount"] = shape[0]
    else:
        assert kind in ('svg', 'png')
        dp["tree_component", "version"] = ""
        dp["ssr_tree_block", "style"] = layout.SHOW
        dp["ssr_tree_img", "src"] = f'/files/{task_id}/ssr_img.{kind}?version={version}'


@add_processor(
    tree_csv_download_on_connection_id = ('trigger_csv_download', 'data')
)
def tree_csv_download(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
    if dp['connection_id', 'data'] != int(upd[db_key]):
        # start download only in one connection
        return
    # we got the command to trigger csv download
    task_id = dp['task_id', 'data']
    # trigger csv download
    dp[dash_keys[0]] = int(upd['csv_render_n'])

    # remove the command for csv download from the db
    while True:
        try:
            with user.db.pipeline(transaction=True) as pipe:
                pipe.watch(f"/tasks/{task_id}/state")
                cur_id = pipe.hget(f"/tasks/{task_id}/state", "tree_csv_download_on_connection_id")
                if cur_id != upd[db_key]:
                    # db already has another tree_csv_download command, ignore
                    return

                pipe.multi()
                # Clear the tree_csv_download command without issuing update
                pipe.hset(f"/tasks/{task_id}/state", db_key, -1)
                pipe.execute()
            break
        except redis.WatchError:
            pass


def gen_progress_keys(stage):
    return (
        (f'{stage}_progress_text', 'children'), #text

        (f'{stage}_progress_bar', 'max'),
        (f'{stage}_progress_bar', 'value'),
        (f'{stage}_progress_bar', 'animated'),
        (f'{stage}_progress_bar', 'striped'),
        (f'{stage}_progress_bar', 'color'),

        (f'{stage}_progress_container', 'style'),
    )


@add_processor(
    progress_table = gen_progress_keys("table"),
    progress_vis = gen_progress_keys("vis"),
    progress_heatmap = (
        *gen_progress_keys("heatmap"),
        ('heatmap_header', 'style')
    ),
    progress_tree = (
        *gen_progress_keys("tree"),
        ('tree_header', 'style')
    ),
    # todo: add all progress bars here
)
def progress(dp: DashProxy, upd: dict[str, str], db_key:str, dash_keys:tuple[tuple[str,str], ...]):
    pbdata = upd[db_key]
    stage = db_key.rsplit("_", maxsplit=1)[-1]
    pb = f'{stage}_progress_bar'
    reveal = {
        'heatmap': ('heatmap_header', 'heatmap_progress_container'),
        'tree': ('tree_header', 'tree_progress_container'),
    }
    # pbdata structure: {
    #     'style': "progress"|"error"|"",
    #     'max': 100,
    #     'value': 100,
    #     'msg': ""
    # }
    style = pbdata.get('style')

    if not style:
        dp[f'{stage}_progress_container', 'style'] = layout.HIDE
        dp[f'{stage}_progress_text', 'children'] = None
        return

    msg = pbdata.get('msg', '')

    for comp in reveal.get(stage, (f'{stage}_progress_container',)):
        dp[comp, 'style'] = layout.SHOW

    if style == 'progress':
        dp[pb, 'color'] = 'info'

        if pbdata.get('max'):
            # todo: accomodate empty strings
            total = pbdata['max']
            value = pbdata.get('value', 0)
            dp[pb, 'max'] = total
            dp[pb, 'value'] = value
            dp[pb, 'animated'] = False
            dp[pb, 'striped'] = False
            if msg:
                msg = f"{msg} ({value}/{total})"
            else:
                msg = f"{value}/{total}"
        else:
            dp[pb, 'max'] = 100
            dp[pb, 'value'] = 100
            dp[pb, 'animated'] = True
            dp[pb, 'striped'] = True
    elif style == 'error':
        dp[pb, 'color'] = 'danger'

        dp[pb, 'max'] = 100
        dp[pb, 'value'] = 100
        dp[pb, 'animated'] = False
        dp[pb, 'striped'] = False
        if not msg:
            msg = "Unknown error"
    else:
        assert False, f'unknown pb style {style}'

    dp[f'{stage}_progress_text', 'children'] = msg



def create_outputs():
    outputs = set()
    for dash_keys, _ in DB_2_DASH.values():
        for dash_key in dash_keys:
            outputs.add(dash_key)
    for id, prop in sorted(outputs):
        yield Output(id, prop)


@dash_proxy.callback(
    Output('progress_updater', 'disabled'),
    Output('cancel-button', 'className'),
    Output('version', 'data'),
    Output('connection_id', 'data'),
    Output('force_update_until', 'data'),

    *create_outputs(),

    Input('progress_updater', 'n_intervals'),
    Input('force_update_submit', 'data'),
    Input('search-prot-button', 'n_clicks'),
    Input('trigger_csv_download_refresh', 'data'),


    State('task_id', 'data'),
    State('connection_id', 'data'),
    State('version', 'data'),

    State('force_update_until', 'data'),
    State('blast-button-input-value', 'data'),
)
def update_everything(dp: DashProxy):
    task_id = dp['task_id', 'data']

    if dp.is_triggered_by(('force_update_submit', 'data')):
        dp['cancel-button', 'className'] = "float-right"
    if dp.is_triggered_by(
        ('search-prot-button', 'n_clicks'),
        ('trigger_csv_download_refresh', 'data')):
        # can't depend that enqueue would be called before update,
        # so force-rechecking for a bit
        dp['force_update_until', 'data'] = time.time()+5

    update_needed = True

    while update_needed:
        # initial load
        with user.db.pipeline(transaction=True) as pipe:
            pipe.hgetall(f"/tasks/{task_id}/enqueued") # stage: qid
            pipe.hlen(f"/tasks/{task_id}/running") # stage: qid
            user.get_updates(task_id, dp['version', 'data'], dp['connection_id', 'data'], redis_client=pipe)

            enqueued, running, updates = pipe.execute()
        updates = user.decode_updates_resp(updates)
        if len(updates) == 2:
            dp['version', 'data'], updates = updates
        else:
            dp['version', 'data'], dp['connection_id', 'data'], updates = updates
        updates: dict[str, str]
        if updates:
            print(f"<- update {dp['version', 'data']}:", updates, flush=True)
        JSON_ENCODED_DATA = {"tree", "tree_opts"}

        for k in JSON_ENCODED_DATA.intersection(updates.keys()):
            if updates[k]:
                updates[k] = json.loads(updates[k])
            else:
                updates[k] = {}

        if enqueued:
            with user.db.pipeline(transaction=True) as pipe:
                for stage, qid in enqueued.items():
                    user.get_queue_pos(
                        queue_key=f"/queues/{stage}",
                        task_q_id=qid,
                        redis_client=pipe,
                    )
                    pipe.hget(f"/tasks/{task_id}/state", f"progress_{stage}_msg")

                res = pipe.execute()
            res_it = iter(res)
            for stage in enqueued:
                pos = next(res_it)
                msg = next(res_it) or stage
                if pos > 0:
                    msg = f"{msg}: {pos} task{'s' if pos>1 else ''} before yours"
                else:
                    msg = f"{msg}: starting"

                updates[f"progress_{stage}_style"] = "progress"
                updates[f"progress_{stage}_msg"] = msg

        dp['progress_updater', 'disabled'] = not (
            enqueued or running or dp['force_update_until', 'data'] > time.time()
        )
        if dp['progress_updater', 'disabled']:
            dp['cancel-button', 'className'] = "float-right d-none"

        # group progress_{stage}_{msg/max/value/style} as
        # dict progress_{stage} with keys {msg/max/value/style}
        for db_key in tuple(filter(lambda x: x.startswith("progress_"), updates.keys())):
            key, subkey = db_key.rsplit("_", maxsplit=1)
            updates.setdefault(key, {})[subkey] = updates.pop(db_key)

        if 'progress_blast' in updates:
            updates['progress_tree'] = updates.pop('progress_blast')
        if 'progress_tree_csv' in updates:
            updates['progress_tree'] = updates.pop('progress_tree_csv')

        update_needed = False

        for db_key in DB_2_DASH_KEYS.intersection(updates):
            dash_keys, func = DB_2_DASH[db_key]
            update_needed = func(dp, updates, db_key, dash_keys) or update_needed
#endregion


@dash_proxy.callback(
    Output('uniprotAC', 'value'),
    Input('uniprotAC_update', 'data'),
    Input('prot-search-result', 'data'),
    State('uniprotAC', 'value'),
)
def uniport_update_multiplexer(dp:DashProxy):
    # I'm really tried of dash limitations...
    if dp.is_triggered_by(('uniprotAC_update', 'data')):
        if dp['uniprotAC_update', 'data'] is not None:
            dp['uniprotAC', 'value'] = dp['uniprotAC_update', 'data']
    if dp.is_triggered_by(('prot-search-result', 'data')):
        cur_val = dp['uniprotAC', 'value'].strip()
        if cur_val:
            dp['uniprotAC', 'value'] = f"{dp['prot-search-result', 'data']}\n{cur_val}"
        else:
            dp['uniprotAC', 'value'] = dp['prot-search-result', 'data']


@dash_proxy.callback(
    Output("wrong-input-msg", "is_open"),
    Output('force_update_submit', 'data'),


    ###
    Input('submit-button', 'n_clicks'),
    Input('rerenderSSR_button', 'n_clicks'),
    Input('cancel-button', 'n_clicks'),
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
    State("max-proteins", "value"),
    State("submit-button", "children"),

    ###
    State('uniprotAC', 'value'),
    State('tax-level-dropdown', 'value'),

    State('connection_id', 'data'),
    ###
)
def submit(dp:DashProxy):
    task_id = dp['task_id', 'data']
    # append prot search result last!
    upd_priority = {
        # ('prot-search-result', 'data'): 100
    }
    triggers = sorted(dp.triggered, key=lambda x: upd_priority.get(x, 0))
    for cause in triggers:
        if cause == ('submit-button', 'n_clicks'):
            # button press triggered
            if dp["blast-options", "is_open"]:
                if dp["pident-input", "invalid"] or dp["qcovs-input", "invalid"]:
                    # client validation failed
                    dp["wrong-input-msg", "is_open"] = True
                    continue
                # performing server validation
                try:
                    pident = float(dp["pident-output-val", "data"])
                    if not (0 < pident <= 100):
                        raise ValueError()
                    qcovs = float(dp["qcovs-output-val", "data"])
                    if not (0 < qcovs <= 100):
                        raise ValueError()
                    evalue = dp["evalue", "value"].strip()
                    if float(evalue) <= 0:
                        raise ValueError()
                except Exception:
                    # client validation succeeded, server validation failed
                    dp["wrong-input-msg", "is_open"] = True
                    continue

                # validation succeeded
                dp["wrong-input-msg", "is_open"] = False
            else:
                # no blast options, set to default ('') for redis request
                qcovs = ''
                pident = ''
                evalue = ''

            assert dp['connection_id', 'data'], "Connection id should be set on page load"

            with user.db.pipeline(transaction=True) as pipe:
                user.enqueue(task_id, "table", redis_client=pipe)
                user.cancel(task_id, "vis", redis_client=pipe)
                user.cancel(task_id, "tree_csv", redis_client=pipe)
                user.cancel(task_id, "blast", redis_client=pipe)
                user.cancel(task_id, "ssr", redis_client=pipe)

                user.update(
                    task_id, connection_id=dp['connection_id', 'data'], redis_pipe=pipe,

                    progress_table_style='',
                    progress_table_msg="Building table",
                    input_proteins=dp['uniprotAC', 'value'],
                    input_tax_level=dp['tax-level-dropdown', 'value'],
                    input_blast_enabled="1" if dp["blast-options", "is_open"] else "",
                    input_blast_evalue=evalue,
                    input_blast_pident=pident,
                    input_blast_qcovs=qcovs,
                    input_max_proteins=dp["max-proteins", "value"],
                )
                res = pipe.execute()
                dp['force_update_submit', 'data'] = True

        elif cause == ('rerenderSSR_button', 'n_clicks'):
            raise NotImplementedError("SSR needs to be updated")
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
                        'total': -2,
                        "message": "Rerendering",
                    }
                )
                res = pipe.execute()
            dp['tree_version_target', 'data'] = decode_int(res[0][0])

        elif cause == ('cancel-button', 'n_clicks'):
            with user.db.pipeline(transaction=True) as pipe:
                user.cancel(task_id, "table", redis_client=pipe)
                user.cancel(task_id, "vis", redis_client=pipe)
                user.cancel(task_id, "tree_csv", redis_client=pipe)
                user.cancel(task_id, "blast", redis_client=pipe)
                user.cancel(task_id, "ssr", redis_client=pipe)

                res = pipe.execute()


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
    elif name.lower().endswith(".csv"):
        response.mimetype = "text/csv"
        response.headers["Content-Disposition"] = f'attachment; filename="{name}"'
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



# @dash_app.server.route('/some_non_public_ssr_path')
# def serve_ssr():
#     return flask.send_file(f"/app/ssr/index.html")
