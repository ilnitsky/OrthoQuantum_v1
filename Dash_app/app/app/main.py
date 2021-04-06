import os
import os.path
import re
import time

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

from .app import SPARQL_wrap, presence_img, correlation_img

from . import layout
from . import user

app = flask.Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

dash_app = Dash(__name__, server=app, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.UNITED])
dash_app.layout = layout.index

def login(dst):
    # TODO: dsiplay login layout, login, redirect to the original destintation
    print("register")
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


FASTA_CLEANUP = str.maketrans('', '', '["]')
INVALID_PROT_IDS = re.compile(r"[^A-Za-z0-9\-\n \t]+")

@dash_app.callback(
    Output('output_div', 'children'),
    [Input('submit-button', 'n_clicks')],
    [State('username', 'value'), State('dropdown', 'value')],
)
def update_output(clicks, input_value, dropdown_value):
    if clicks is None:
        # Initial load, don't do anything
        return

    level = dropdown_value.split('-')[0]
    uniprot_ac = INVALID_PROT_IDS.sub("", input_value).upper().split()
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
        filter (?xref in ({', '.join(f'uniprot:{v}' for v in uniprot_ac)}))
        ?gene a :Gene; :memberOf ?og.
        ?gene :xref [a :Xref; :xrefResource ?xref ].
        ?gene :name ?gene_name.
    }}
    """)
    endpoint.setReturnFormat(SPARQLWrapper.JSON)
    n = endpoint.query().convert()

    requested_ids = set(uniprot_ac)
    found_ids = set()

    # Tuples of 'label', 'Name', 'PID'
    data_tuples = []

    for result in n["results"]["bindings"]:
        # yapf: disable
        data_tuples.append(
            (
                result["og"]["value"].split('/')[-1].strip(),
                result["gene_name"]["value"],
                result["gene_name"]["value"],
            )
        )
        # yapf: enable
        prot_id = result["xref"]["value"].rsplit("/", 1)[-1].strip().upper()
        found_ids.add(prot_id)

    missing_ids = requested_ids - found_ids

    # if requested_ids is not empty - adding more data via slow request
    if missing_ids:
        for uniprot_name in missing_ids:
            try:
                resp = requests.get(f"http://www.uniprot.org/uniprot/{uniprot_name}.fasta").text
                fasta_query = "".join(resp.split("\n")[1:])[:100]
                resp = requests.get(f"https://v101.orthodb.org/blast?level=2&species=2&seq={fasta_query}&skip=0&limit=100").text
                og_handle = resp.split(",")[2].split(":")[1]
                og_handle = og_handle.translate(FASTA_CLEANUP).strip()
                # yapf: disable
                data_tuples.append(
                    (
                        og_handle,
                        og_handle,
                        uniprot_name,
                    )
                )
                # yapf: enable
            except Exception:
                # TODO: log something?
                pass
            else:
                found_ids.add(uniprot_name)
        missing_ids = requested_ids - found_ids

        if missing_ids:
            # TODO: tried 2 methods, couldn't find the data for these IDs. Report to user?
            print(f"Missing IDs: {', '.join(missing_ids)}")

    uniprot_df = pd.DataFrame(columns=['label', 'Name', 'PID'], data=data_tuples)
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

    og_string = ', '.join(f'odbgroup:{og}' for og in og_list)

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

    # yapf: disable
    og_info = (
        tuple(
            res[col]["value"]
            for col in dash_columns
        )
        for res in result["results"]["bindings"]
    )
    # yapf: enable

    og_info_df = pd.DataFrame(og_info, columns=dash_columns)
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

    return dash_table.DataTable(data=dash_data, columns=dash_columns, filter_action="native")


@dash_app.callback(
    Output('output_div2', 'children'),
    [Input('submit-button2', 'n_clicks'), Input('dropdown2', 'value')],
)
def call(clicks, level):
    if clicks is None:
        return

    SPARQL_wrap(level)
    corri = correlation_img(level)
    concat, presi = presence_img(level)

    t = time.time()
    # HACK: nocache={t} is untill each image has a unique name
    return html.Div([
        dbc.Row([
            dbc.Col([dbc.Col(html.Div(
                html.Img(src=f'{corri}?nocache={t}')
            ))]),
            dbc.Col([dbc.Col(html.Div(
                html.Img(src=f'{presi}?nocache={t}', style={'height': '612px', 'width': '200px'})
            ))]),
        ]),
        dbc.Row([
            dbc.Col([]),
            dbc.Col([html.Img(src=f'{concat}?nocache={t}', style={'width': '1500px'})]),
            dbc.Col([]),
        ])
    ])


@dash_app.server.route('/files/<uid>/<name>')
def serve_user_file(uid, name):
    if flask.session.get("USER_ID", '') != uid:
        flask.abort(403)
    response = flask.make_response(flask.send_from_directory(user.path(), name))
    response.headers["Cache-Control"] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response
