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
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from werkzeug.serving import run_simple

import numpy

from SPARQLWrapper import SPARQLWrapper, JSON
import pandas as pd

import requests

from app import SPARQLWrap, Presence_Img, Correlation_Img
from navbar import Navbar

import ssl  #pylint: disable=wrong-import-order
if (not os.environ.get('PYTHONHTTPSVERIFY') and getattr(ssl, '_create_unverified_context', None)):
    ssl._create_default_https_context = ssl._create_unverified_context  #pylint: disable=protected-access

nav = Navbar()

# from homepage import Homepage

server = flask.Flask(__name__)
dash_app1 = Dash(__name__, server=server, routes_pathname_prefix='/dashboard/', external_stylesheets=[dbc.themes.UNITED])
dash_app2 = Dash(__name__, server=server, routes_pathname_prefix='/reports/', external_stylesheets=[dbc.themes.UNITED])
dash_app3 = Dash(__name__, server=server, routes_pathname_prefix='/blast/', external_stylesheets=[dbc.themes.UNITED])

#  url_base_pathname='/dashboard/',

body = dbc.Container(
    [
        dbc.Row([
            dbc.Col(
                [
                    html.H2("Heading"),
                    html.P("""Download presence and study orthology group presence.
                            Use UniProt Acccesion Codes of your proteins to create a list with corresponding
                            Orthology groups"""),
                    dbc.Button("View details", color="secondary"),
                ],
                md=4,
            ),
            html.Br(),
            html.Br(),
            dbc.Col([
                html.H2("___________________________________"),
                html.P("""Input protein IDs in the textarea and select current taxonomy (level of orthology)"""),
            ]),
        ])
    ],
    className="mt-4",
)

og_from_input = html.Div(children=[
    dbc.Row([
        dbc.Col(html.Div("")),
        dbc.Col(
            html.Div([
                dcc.Dropdown(options=[
                    {
                        'label': 'Eukaryota (compact)',
                        'value': 'Eukaryota'
                    },
                    {
                        'label': 'Eukaryota (all species)',
                        'value': 'Eukaryota-full'
                    },
                    {
                        'label': 'Metazoa',
                        'value': 'Metazoa'
                    },
                    {
                        'label': 'Vertebrata',
                        'value': 'Vertebrata'
                    },
                    {
                        'label': 'Tetrapoda',
                        'value': 'Tetrapoda'
                    },
                    {
                        'label': 'Actinopterygii',
                        'value': 'Actinopterygii'
                    },
                    {
                        'label': 'Bacteria (all 5500 species)',
                        'value': 'Bacteria'
                    },
                    {
                        'label': 'Protista',
                        'value': 'Protista'
                    },
                    {
                        'label': 'Archaea',
                        'value': 'Archaea'
                    },
                    {
                        'label': 'Fungi',
                        'value': 'Fungi'
                    },
                    {
                        'label': 'Viridiplantae',
                        'value': 'Viridiplantae'
                    },
                    {
                        'label': 'Aves',
                        'value': 'Aves'
                    },
                ],
                             placeholder="Select a taxon (level of orthology)",
                             value='Vertebrata',
                             id='dropdown'),
                html.Div(id='dd-output-container')
            ])),
        dbc.Col(html.Div())
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col(html.Div()),
        dbc.Col(
            html.Div([
                dcc.Textarea(id='username', placeholder='This app uses Uniprot AC (Accession Code): for example "Q91W36" ', value='', rows=6, style={'width': '100%'}),
                html.Button(id='submit-button', type='submit', children='Submit'),
                html.Button(id='su', type='submit', children='From .txt File'),
            ])),
        dbc.Col(html.Div(dcc.Loading(
            id="loading-2",
            children=[html.Div([html.Div(id="loading-output-2")])],
            type="circle",
        ))),
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col(html.Div()),
        dbc.Col(html.Div(dbc.Progress(id='progress', striped=True, animated=True))),
        dbc.Col(html.Div()),
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col(html.Div()),
        dbc.Col(html.Div(id='output_div')),
        dbc.Col(html.Div()),
    ]),
    html.Br(),
    html.Br(),
    dbc.Row([
        dbc.Col(html.Div("")),
        dbc.Col(
            html.Div([
                dcc.Dropdown(options=[
                    {
                        'label': 'Eukaryota (compact)',
                        'value': 'Eukaryota'
                    },
                    {
                        'label': 'Eukaryota (all species)',
                        'value': 'Eukaryota-full'
                    },
                    {
                        'label': 'Metazoa',
                        'value': 'Metazoa'
                    },
                    {
                        'label': 'Vertebrata',
                        'value': 'Vertebrata'
                    },
                    {
                        'label': 'Tetrapoda',
                        'value': 'Tetrapoda'
                    },
                    {
                        'label': 'Actinopterygii',
                        'value': 'Actinopterygii'
                    },
                    {
                        'label': 'Bacteria (all 5500 species)',
                        'value': 'Bacteria-full'
                    },
                    {
                        'label': 'Protista',
                        'value': 'Protista'
                    },
                    {
                        'label': 'Archaea',
                        'value': 'Archaea'
                    },
                    {
                        'label': 'Fungi',
                        'value': 'Fungi'
                    },
                    {
                        'label': 'Viridiplantae',
                        'value': 'Viridiplantae'
                    },
                    {
                        'label': 'Aves',
                        'value': 'Aves'
                    },
                    {
                        'label': 'Nicotiana',
                        'value': 'Nicotiana'
                    },
                ],
                             placeholder="Select a taxon (level of orthology)",
                             value='Vertebrata',
                             id='dropdown2'),
                html.Div(id='dd2-output-container')
            ])),
        dbc.Col(html.Div())
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col(html.Div()),
        dbc.Col([html.Button(id='submit-button2', type='submit', children='Go')]),
        dbc.Col(html.Div(

            # dcc.Location(id = 'url', refresh = True),
            # html.Div(id = 'page-content')
        )),
    ]),
])


#D A S H   A P P 1  L A Y O U T
def homepage():
    layout = html.Div([
        nav,
        body,
        html.Br(),
        html.Br(),
        og_from_input,
        html.Div(id='output_div2'),
        dcc.Link('Navigate to "Images"', href='/reports'),
        # html.Img(src=r'C:\Users\nfsus\OneDrive\best_repository_ever\Dash_app\assets\images\Correlation.png')
    ])
    return layout


#D A S H   A P P 2  L A Y O U T
def page_2():
    layout = html.Div([
        nav,
        body2,
        html.Div([
            # dcc.Dropdown(
            #     id='image-dropdown',
            #     options=[{'label': i, 'value': i} for i in list_of_images],
            #     value=list_of_images[0]
            # ),
            # html.Img(id='image')
        ])
    ])
    return layout


#D A S H  A P P 3  L A Y O U T
def blast_layout():
    layout = html.Div([
        nav,
        body,
        html.Div(id='1'),
    ])
    return layout


dash_app1.config['suppress_callback_exceptions'] = True

dash_app2.config['suppress_callback_exceptions'] = True

dash_app3.config['suppress_callback_exceptions'] = True

dash_app1.layout = homepage()

dash_app3.layout = blast_layout()

endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")


@dash_app1.callback(Output('dd-output-container', 'children'), [Input('dropdown', 'value')])
def select_level(value):
    level = value
    return 'Selected "{}" orthology level'.format(value)


@dash_app1.callback(
    Output('output_div', 'children'),
    [Input('submit-button', 'n_clicks')],
    [State('username', 'value'), State('dropdown', 'value')],
)
def update_output(clicks, input_value, dropdown_value):

    if clicks is not None:

        if os.path.isfile("SPARQLWrapper.csv"):
            os.remove("SPARQLWrapper.csv")

        level_copy = dropdown_value

        level = dropdown_value
        level = str(level.split('-')[0])
        input_list = input_value.split()
        # u = UniProt()
        # Prot_IDs = []
        # for Entry in input_list:
        #     res = u.search('id:' + str(Entry).strip() + ' AND taxonomy:"Mammalia [40674]"',
        #     frmt='tab', columns='entry name, length, id, genes(PREFERRED)')
        #     if not res:
        #         res = 'NotFound'
        #     else:
        #         res = res.split('\n')[1].split('\t')[-1]
        #     Prot_IDs.append(res)

        uniprot_ac = input_list
        # uniprot_name = Prot_IDs
        uniprot_ac = [x.strip() for x in uniprot_ac]

        results = []
        i = 0
        P = []
        L = []
        M = []

        uniprot_ac_string = ''
        for i in uniprot_ac:
            uniprot_ac_string = uniprot_ac_string + 'uniprot:' + str(i) + ', '
        uniprot_ac_string = uniprot_ac_string[:-2]

        query = """
        prefix : <http://purl.orthodb.org/>
        select ?og  ?og_description ?gene_name
        where {
        ?og a :OrthoGroup;
        :ogBuiltAt [up:scientificName "%s"];
        :name ?og_description;
        !:memberOf/:xref/:xrefResource ?xref .
        filter (?xref in (%s))
        ?gene a :Gene; :memberOf ?og.
        ?gene :xref [a :Xref; :xrefResource ?xref ].
        ?gene :name ?gene_name.
        }
        """ % (level, uniprot_ac_string)
        # print(query)
        endpoint.setQuery(query)
        endpoint.setReturnFormat(JSON)
        n = endpoint.query().convert()

        for Y in n["results"]["bindings"]:
            og_Y_list = []
            # gene_name_list = []
            og_Y = Y["og"]["value"].split('/')[-1]
            gene_name_Y = Y["gene_name"]["value"]
            og_Y_list.append(og_Y)
            M.append(og_Y_list[0])
            L.append(gene_name_Y)
            P.append(gene_name_Y)
        results.append(endpoint.query().convert())

        uniprot_df = pd.DataFrame(columns=['label', 'Name', 'PID'])
        data_tuples = list(zip(M, L, P))
        uniprot_df = pd.DataFrame(columns=['label', 'Name', 'PID'], data=data_tuples)
        uniprot_df['is_duplicate'] = uniprot_df.duplicated(subset='label')

        if uniprot_df.empty:
            for i in range(len(uniprot_ac)):
                handle_1 = requests.get("http://www.uniprot.org/uniprot/{}.fasta".format(uniprot_ac[i]))
                fasta_query = ("").join(handle_1.text.split("\n")[1:])[0:100]
                handle_2 = requests.get("https://v101.orthodb.org/blast?level=2&species=2&seq={}&skip=0&limit=100".format(fasta_query))
                og_handle = handle_2.text.split(",")[2].split(":")[1]
                og_handle = og_handle.translate({ord(i): None for i in '["]'}).strip()
                M.append(og_handle)
                L.append(og_handle)
                P.append(uniprot_ac[i])
                print(i)
            data_tuples = list(zip(M, L, P))
            uniprot_df = pd.DataFrame(columns=['label', 'Name', 'PID'], data=data_tuples)
            uniprot_df = uniprot_df.replace("", numpy.nan)
            uniprot_df = uniprot_df.dropna(axis="index", how="any")
            uniprot_df['is_duplicate'] = uniprot_df.duplicated(subset='label')

        print(uniprot_df)

        K = []
        J = []
        H = []
        for row in uniprot_df.itertuples(index=True, name='Pandas'):
            if not row.is_duplicate:
                rowlist1 = uniprot_df[uniprot_df.label == str(row.label)].Name.tolist()

                #remove duplicate names
                rowlist2 = []
                for i in rowlist1:
                    if i not in rowlist2:
                        rowlist2.append(i)

                K.append("-".join(rowlist2))
                J.append(row.label)
                H.append(row.PID)

        #SPARQL Look For Presence of OGS in Species
        OG_list = J
        data_tuples = list(zip(J, K, H))
        uniprot_df = pd.DataFrame(columns=['label', 'Name', 'UniProt_AC'], data=data_tuples)
        uniprot_df.to_csv('OG.csv', sep=';', index=False)

        #make query string from given OGs
        strng = ''
        for i in OG_list:
            strng = strng + 'odbgroup:' + str(i) + ', '
        strng = strng[:-2]

        #SPARQL query
        results = []
        query = """
        prefix : <http://purl.orthodb.org/>
        select *
        where {
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
        optional { ?og :ogMedianProteinLength ?medianProteinLength}
        optional { ?og :ogStddevProteinLength ?stddevProteinLength}
        optional { ?og :ogMedianExonsCount ?medianExonsCount}
        optional { ?og :ogStddevExonsCount ?stddevExonsCount}
        filter (?og in (%s))
        }
            """ % (strng)

        endpoint.setQuery(query)
        endpoint.setReturnFormat(JSON)
        results.append(endpoint.query().convert())

        col = [
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

        og_info = [[]]

        for p in results:
            for res in p["results"]["bindings"]:
                og_info_row = []
                for k in col:
                    og_info_row.append(res[k]["value"])
                og_info.append(og_info_row)

        og_info_df = pd.DataFrame(og_info, columns=col)
        og_info_df = pd.merge(og_info_df, uniprot_df, on='label')

        # pd.to_numeric(og_info_df["totalGenesCount"])
        # pd.to_numeric(og_info_df["multiCopyGenesCount"])
        # pd.to_numeric(og_info_df["singleCopyGenesCount"])

        # og_info_df["paralogs_count"] = ( og_info_df["totalGenesCount"] - og_info_df["multiCopyGenesCount"] ) / og_info_df["singleCopyGenesCount"]

        cols2 = [
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
        og_info_df = og_info_df[cols2]

        #prepare datatable update
        data = og_info_df.to_dict('records')
        columns = [{
            "name": i,
            "id": i,
        } for i in og_info_df.columns]

        return dash_table.DataTable(data=data, columns=columns, filter_action="native")


@dash_app1.callback(
    Output('output_div2', 'children'),
    [Input('submit-button2', 'n_clicks'), Input('dropdown2', 'value')],
)
def call(clicks, dropdown_value):
    if clicks is not None:
        level = dropdown_value

        SPARQLWrap(level)
        corri = Correlation_Img(level)
        presi = Presence_Img(level)

        encoded_string = ""
        with open('assets/images/concat_phylo.png', 'rb') as image_file:

            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            zie = encoded_string

        layout = html.Div([dbc.Row([
            dbc.Col([dbc.Col(html.Div(corri))]),
            dbc.Col([dbc.Col(html.Div(presi))]),
        ]), dbc.Row([
            dbc.Col([]),
            dbc.Col([html.Img(src='data:image/png;base64,{}'.format(zie), style={'width': '1500px'})]),
            dbc.Col([]),
        ])])

        return layout


IMAGE_DIRECTORY = 'assets/images/'
list_of_images = [os.path.basename(x) for x in glob.glob('{}*.png'.format(IMAGE_DIRECTORY))]
# print(list_of_images)
STATIC_IMAGE_ROUTE = '/static/'

body2 = dbc.Container(
    [
        dbc.Row([
            dbc.Col(
                [
                    html.H2("Image outputs"),
                    html.P("""Download presence and study orthology group presence"""),
                    #    dbc.Button("View details", color="secondary"),
                ],
                md=4,
            ),
            dbc.Col([]),
        ])
    ],
    className="mt-4",
)

endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")

dash_app2.layout = page_2()


@dash_app2.callback(dash.dependencies.Output('image', 'src'), [dash.dependencies.Input('image-dropdown', 'value')])
def update_image_src(value):
    return STATIC_IMAGE_ROUTE + value


@dash_app2.server.route('{}<image_path>.png'.format(STATIC_IMAGE_ROUTE))
def serve_image(image_path):
    image_name = '{}.png'.format(image_path)
    if image_name not in list_of_images:
        raise Exception('"{}" is excluded from the allowed static files'.format(image_path))
    return flask.send_from_directory(IMAGE_DIRECTORY, image_name)


# @server.route('/')
# @server.route('/hello')
def hello():
    return 'Root page'


@server.route('/dashboard')
def render_dashboard():
    return flask.redirect('/dash1')


@server.route('/reports')
def render_reports():
    return flask.redirect('/dash2')


@server.route('/blast')
def render_blast():
    return flask.redirect('/dash3')


app = DispatcherMiddleware(server, {'/dash1': dash_app1.server, '/dash2': dash_app2.server, '/dash3': dash_app3.server})

run_simple('0.0.0.0', 8050, app, use_reloader=True, use_debugger=True)
