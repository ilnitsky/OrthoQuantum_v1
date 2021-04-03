import base64
import os
import os.path
import glob

import dash
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

from .app import SPARQLWrap, Presence_Img, Correlation_Img

from . import layout
from . import user


# TODO: Works without this. Probably best not to mess with ssl
# import ssl  #pylint: disable=wrong-import-order
# if (not os.environ.get('PYTHONHTTPSVERIFY') and getattr(ssl, '_create_unverified_context', None)):
#     ssl._create_default_https_context = ssl._create_unverified_context  #pylint: disable=protected-access



app = flask.Flask(__name__)
app.secret_key = b"SECRET_KEY_CHANGE_ME"

dash_app = Dash(__name__, server=app, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.UNITED])
dash_app.layout = layout.index

def login(dst):
    # TODO: actually log in someone
    user.register()
    return dcc.Location(pathname=dst, id="some_id", refresh=True)


@dash_app.callback(Output('page-content', 'children'), [Input('url', 'pathname')])
def display_page(pathname):
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


# XXX: need this?
@dash_app.callback(Output('dd-output-container', 'children'), [Input('dropdown', 'value')])
def select_level(value):
    return f'Selected "{value}" orthology level'


FASTA_CLEANUP = str.maketrans('', '', '["]')


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
    uniprot_ac = input_value.upper().split()

    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

    # TODO: think about possible injection here (filter by letters and numbers only?)
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
                # XXX: why only 100 letters
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
                # XXX: log something?
                pass
            else:
                found_ids.add(uniprot_name)
        missing_ids = requested_ids - found_ids

        if missing_ids:
            # XXX: tried 2 methods, couldn't find the IDs. Report to user?
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

    SPARQLWrap(level)
    corri = Correlation_Img(level)
    presi = Presence_Img(level)

    encoded_string = ""
    with open('assets/images/concat_phylo.png', 'rb') as image_file:

        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        zie = encoded_string

    return html.Div([dbc.Row([
        dbc.Col([dbc.Col(html.Div(corri))]),
        dbc.Col([dbc.Col(html.Div(presi))]),
    ]), dbc.Row([
        dbc.Col([]),
        dbc.Col([html.Img(src='data:image/png;base64,{}'.format(zie), style={'width': '1500px'})]),
        dbc.Col([]),
    ])])


IMAGE_DIRECTORY = 'assets/images/'
list_of_images = [os.path.basename(x) for x in glob.glob('{}*.png'.format(IMAGE_DIRECTORY))]
# print(list_of_images)
STATIC_IMAGE_ROUTE = '/static/'


@dash_app.callback(dash.dependencies.Output('image', 'src'), [dash.dependencies.Input('image-dropdown', 'value')])
def update_image_src(value):
    return STATIC_IMAGE_ROUTE + value


@dash_app.server.route('{}<image_path>.png'.format(STATIC_IMAGE_ROUTE))
def serve_image(image_path):
    image_name = '{}.png'.format(image_path)
    if image_name not in list_of_images:
        raise Exception('"{}" is excluded from the allowed static files'.format(image_path))
    return flask.send_from_directory(IMAGE_DIRECTORY, image_name)