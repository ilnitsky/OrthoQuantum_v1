from collections import defaultdict
import os
import os.path
import re
import time
import json
import itertools

from dash import Dash
from dash.dependencies import Input, Output, State
import dash_table
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

import flask

import SPARQLWrapper
import pandas as pd

import requests

import phydthree_component

from .app import SPARQL_wrap, presence_img, correlation_img

from . import layout
from . import user

app = flask.Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]


CACHE_TTL = 3*30*24*60*60 # 90 days
# CACHE_TTL = 20 # 20 sec

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


@dash_app.callback(Output('page-content', 'children'), [Input('url', 'pathname')])
def router_page(pathname):
    pathname = pathname.rstrip('/')
    if pathname == '/dashboard':
        if not user.is_logged_in():
            return login(pathname)
        return layout.dashboard
    if pathname == '/reports':
        return layout.reports
    if pathname == '/blast':
        return layout.blast

    return '404'


# TODO: need this?
@dash_app.callback(Output('dd-output-container', 'children'), [Input('dropdown', 'value')])
def select_level(value):
    return f'Selected "{value}" orthology level'


INVALID_PROT_IDS = re.compile(r"[^A-Za-z0-9\-\n \t]+")


def orthodb_get(level:str, prot_ids:list):
    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

    # TODO: think about possible injection here (filter by letters and numbers only?)
    # using INVALID_PROT_IDS to filter all of the nasty possible chars.
    # which are allowed symblos for `level`?
    endpoint.setQuery(f"""
    prefix : <http://purl.orthodb.org/>
    select ?og ?og_description ?gene_name ?xref
    where {{
        ?og a :OrthoGroup;
        :ogBuiltAt [up:scientificName "{level}"];
        :name ?og_description;
        !:memberOf/:xref/:xrefResource ?xref
        filter (?xref in ({', '.join(f'uniprot:{v}' for v in prot_ids)}))
        ?gene a :Gene; :memberOf ?og.
        ?gene :xref [a :Xref; :xrefResource ?xref ].
        ?gene :name ?gene_name.
    }}
    """)
    endpoint.setReturnFormat(SPARQLWrapper.JSON)
    n = endpoint.query().convert()

    # # Tuples of 'label', 'Name', 'PID'
    res = defaultdict(list)

    for result in n["results"]["bindings"]:
        prot_id = result["xref"]["value"].rsplit("/", 1)[-1].strip().upper()
        res[prot_id].append((
            result["og"]["value"].split('/')[-1].strip(),
            result["gene_name"]["value"],
            result["gene_name"]["value"],
        ))

    return res

def uniprot_get(prot_ids:set):
    res = defaultdict(list)
    for prot_id in prot_ids:
        try:
            resp = requests.get(f"http://www.uniprot.org/uniprot/{prot_id}.fasta").text
            fasta_query = "".join(resp.split("\n")[1:])[:100]
            resp = requests.get(f"https://v101.orthodb.org/blast", params={
                "level": 2,
                "species": 2,
                "seq": fasta_query,
                "skip": 0,
                "limit": 1,
            }).json()
            # Throws exception if not found
            og_handle = resp["data"][0]

            res[prot_id].append((
                og_handle,
                og_handle,
                prot_id,
            ))
        except Exception:
            pass
    return res


def get_prots(level:str, requested_ids:list):
    prots = defaultdict(list)

    results = user.db.mget(tuple(
        f"/cache/uniprot/{level}/{prot_id}"
        for prot_id in requested_ids
    ))
    for prot_id, cache_res in zip(requested_ids, results):
        if cache_res:
            prots[prot_id] = json.loads(cache_res)
    print(f"From cache {prots=}")
    cache_misses = [
        rid
        for rid in requested_ids
        if rid not in prots.keys()
    ]
    if cache_misses:
        prots.update(orthodb_get(level, cache_misses))
        print(f"From orthodb {prots=}")
        sparql_misses = cache_misses - prots.keys()
        if sparql_misses:
            prots.update(uniprot_get(sparql_misses))
            print(f"From uniprot {prots=}")

    # using pipeline to avoid makeing many small requests
    with user.db.pipeline(transaction=False) as pipe:
        new_keys = cache_misses & prots.keys()
        # Add all new prots to the cache
        for prot_id in new_keys:
            pipe.set(
                f"/cache/uniprot/{level}/{prot_id}",
                json.dumps(prots[prot_id], separators=(',', ':')),
            )
        # set TTL for all new prots
        for prot_id in prots.keys():
            pipe.expire(f"/cache/uniprot/{level}/{prot_id}", CACHE_TTL)

        pipe.execute()

    return prots


@dash_app.callback(
    Output('output_div', 'children'),
    [Input('submit-button', 'n_clicks')],
    [State('username', 'value'), State('dropdown', 'value')],
)
def update_output(clicks, input_value, dropdown_value):
    if clicks is None:
        # Initial load, don't do anything
        return
    # TODO: level is related to prot id?
    level = dropdown_value.split('-')[0]

    requested_ids = list(dict.fromkeys( # removing duplicates
        INVALID_PROT_IDS.sub("", input_value).upper().split(),
    ))

    prots = get_prots(level, requested_ids)

    uniprot_df = pd.DataFrame(
        columns=['label', 'Name', 'PID'],
        data=itertools.chain.from_iterable(prots.values()),
    )
    uniprot_df.replace("", float('nan'), inplace=True)
    uniprot_df.dropna(axis="index", how="any", inplace=True)
    uniprot_df['is_duplicate'] = uniprot_df.duplicated(subset='label')

    og_list = []
    names = []
    uniprot_ACs = []

    # TODO: DataFrame.groupby would be better, but need an example to test
    for row in uniprot_df[uniprot_df.is_duplicate == False].itertuples():
        dup_row_names = uniprot_df[uniprot_df.label == row.label].Name.unique()
        og_list.append(row.label)
        names.append("-".join(dup_row_names))
        uniprot_ACs.append(row.PID)

    #SPARQL Look For Presence of OGS in Species
    uniprot_df = pd.DataFrame(columns=['label', 'Name', 'UniProt_AC'], data=zip(og_list, names, uniprot_ACs))

    uniprot_df.to_csv(user.path()/'OG.csv', sep=';', index=False)

    dash_columns = [
        "label",
        "description",
        "clade",
        "evolRate",
        "totalGenesCount",
        "multiCopyGenesCount",
        "singleCopyGenesCount",
        "inSpeciesCount",
        # "medianExonsCount", "stddevExonsCount",
        "medianProteinLength",
        "stddevProteinLength",
        "og"
    ]

    cache_misses = []

    og_info = defaultdict(dict)

    with user.db.pipeline(transaction=False) as pipe:
        for og in og_list:
            pipe.hmget(f"/cache/ortho/{og}", dash_columns)

        for og, data in zip(og_list, pipe.execute()):
            for col_name, val in zip(dash_columns, data):
                if val is None:
                    cache_misses.append(og)
                    break
                og_info[og][col_name] = val.decode()

    print(f"{og_info=}")
    print(f"{cache_misses=}")


    if cache_misses:
        og_string = ', '.join(f'odbgroup:{og}' for og in cache_misses)

        endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

        #SPARQL query
        endpoint.setQuery(f"""
        prefix : <http://purl.orthodb.org/>
        select *
        where {{
        ?og a :OrthoGroup;
            rdfs:label ?label;
            :name ?description;
            :ogBuiltAt [up:scientificName ?clade];
            :ogEvolRate ?evolRate;
            :ogPercentSingleCopy ?percentSingleCopy;
            :ogPercentInSpecies ?percentInSpecies;
            :ogTotalGenesCount ?totalGenesCount;
            :ogMultiCopyGenesCount ?multiCopyGenesCount;
            :ogSingleCopyGenesCount ?singleCopyGenesCount;
            :ogInSpeciesCount ?inSpeciesCount;
            :cladeTotalSpeciesCount ?cladeTotalSpeciesCount .
        optional {{ ?og :ogMedianProteinLength ?medianProteinLength}}
        optional {{ ?og :ogStddevProteinLength ?stddevProteinLength}}
        optional {{ ?og :ogMedianExonsCount ?medianExonsCount}}
        optional {{ ?og :ogStddevExonsCount ?stddevExonsCount}}
        filter (?og in ({og_string}))
        }}
        """)
        endpoint.setReturnFormat(SPARQLWrapper.JSON)
        result = endpoint.query().convert()

        for og, data in zip(cache_misses, result["results"]["bindings"]):
            for field in dash_columns:
                og_info[og][field] = data[field]["value"]


    with user.db.pipeline(transaction=False) as pipe:
        for og in cache_misses:
            pipe.hmset(f"/cache/ortho/{og}", og_info[og])
        for og in og_info.keys():
            pipe.expire(f"/cache/ortho/{og}", CACHE_TTL)
        pipe.execute()

    print(f"{og_info=}")

    og_info_df = pd.DataFrame(
        (
            vals.values()
            for vals in og_info.values()
        ),
        columns=dash_columns,
    )
    og_info_df = pd.merge(og_info_df, uniprot_df, on='label')

    display_columns = [
        "label",
        "Name",
        "description",
        "clade",
        "evolRate",
        "totalGenesCount",
        "multiCopyGenesCount",
        "singleCopyGenesCount",
        "inSpeciesCount",
        # "medianExonsCount", "stddevExonsCount",
        "medianProteinLength",
        "stddevProteinLength"
    ]
    og_info_df = og_info_df[display_columns]

    #prepare datatable update
    dash_data = og_info_df.to_dict('records')
    dash_columns = [
        {
            "name": i,
            "id": i,
        }
        for i in og_info_df.columns
    ]

    data = []
    missing_ids = requested_ids - prots.keys()
    if missing_ids:
        data.append(
            dbc.Alert(
                [f"Unknown proteins: {', '.join(missing_ids)}"],
                className="alert-warning",
            )
        )
    data.append(
        dash_table.DataTable(data=dash_data, columns=dash_columns, filter_action="native"),
    )
    return html.Div(data)


@dash_app.callback(
    Output('output_div2', 'children'),
    [Input('submit-button2', 'n_clicks'), Input('dropdown2', 'value')],
)
def call(clicks, level):
    if clicks is None:
        return

    SPARQL_wrap(level)
    corri = correlation_img(level)
    pres_xml_url = presence_img(level)

    t = time.time()
    # HACK: nocache={t} is untill each image has a unique name
    return html.Div([
        dbc.Row([
            dbc.Col([dbc.Col(html.Div(
                html.Img(src=f'{corri}?nocache={t}', id="corr")
            ))]),
            # dbc.Col([dbc.Col(html.Div(
            #     html.Img(src=f'{presi}?nocache={t}', style={'height': '612px', 'width': '200px'})
            # ))]),
        ]),

        dbc.Row([
            dbc.Col([phydthree_component.PhydthreeComponent(
                        url=f'{pres_xml_url}?nocache={t}'
                    )]),
        ])
    ])


@dash_app.server.route('/files/<uid>/<name>')
def serve_user_file(uid, name):
    if flask.session.get("USER_ID", '') != uid:
        flask.abort(403)
    response = flask.make_response(flask.send_from_directory(user.path(), name))
    if name.lower().endswith(".xml"):
        response.mimetype = "text/xml"
    response.headers["Cache-Control"] = 'no-store, no-cache, must-revalidate, max-age=0'

    return response
