import json

import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash_html_components.Div import Div

from ..user import db
from ..utils import DEBUG

DROPDOWN_OPTIONS = [
    {
        'label': name,
        'value': id,
    }
    for name, id in json.loads(db.get("/availible_levels")).items()
]
nav_children = [
    dbc.NavItem(dbc.NavLink("Login", href="/blast")),
    dbc.DropdownMenu(
        nav=True,
        in_navbar=True,
        label="Menu",
        children=[
            dbc.DropdownMenuItem(dbc.NavLink("Heatmap Correlation", href="/correlation")),
            dbc.DropdownMenuItem("Presence", href="/reports"),
            dbc.DropdownMenuItem(divider=True),
            dbc.DropdownMenuItem("Entry 3"),
        ],
    ),
]
if DEBUG:
    nav_children.insert(0, dbc.NavItem(dbc.NavLink("Flush Cache", id="flush-button")),)

navbar = dbc.NavbarSimple(
    children=nav_children,
    brand="Home",
    brand_href="/",
    sticky="top",
)

body = dbc.Container(
    [
        dbc.Row([
            dbc.Col([
                html.H2("OrthoQuantum v1.0"),
            ], md=4),
            dbc.Col([
                html.Hr(style={
                    "margin-top": "2rem",
                    "margin-bottom": "0",
                }),
            ], md=8),
        ]),
        dbc.Row([
            dbc.Col(
                [
                    html.P("""Download presence and study orthology group presence.
                            Use UniProt Accesion Codes of your proteins to create a list with corresponding
                            Orthology groups"""),
                    dbc.Button("View tutorial", color="secondary", href="/blast"),
                ],
                md=4,
            ),
            html.Br(),
            html.Br(),
            dbc.Col([
                    html.P("""Input protein IDs in the textarea and select current taxonomy (level of orthology)"""),
                ],
                md=8,
            ),
        ])
    ],
    className="mt-4",
)

og_from_input = html.Div(children=[
    dbc.Row([
            dbc.Col(
                html.Div([
                    dcc.Dropdown(
                        placeholder="Select a taxon (level of orthology)",
                        value='4',
                        id='dropdown',
                        options=DROPDOWN_OPTIONS,
                    )
                ]),
                md=8,
                lg=6,
            ),
        ],
        justify='center',
    ),
    html.Br(),
    dbc.Row([
        dbc.Col(
            html.Div([
                dcc.Textarea(id='uniprotAC', placeholder='This app uses Uniprot AC (Accession Code): for example "Q91W36" ', value='', rows=6, style={'width': '100%'}),
                html.Button(id='submit-button', type='submit', children='Submit'),
                # html.Button(id='su', type='submit', children='From .txt File'),
            ]),
            md=8,
            lg=6,
        ),
    ], justify='center'),
    html.Br(),
    html.Br(),
    dbc.Row(
        dbc.Col(
            dbc.Alert(
                id="missing_prot_alert",
                is_open=False,
                className="alert-warning",
            ),
            md=8, lg=6,
        ),
        justify='center',
    ),
    dbc.Row(
        dbc.Col(
            id='table_progress_container',
            md=8, lg=6,
        ),
        justify='center'),
    dcc.Store(id='table_version', data=0),
    dbc.Row(
        dbc.Col(
            html.Div(
                id="table_container",
                className="pb-3",
            ),
            md=12,
        ),
        justify='center',
    ),
    html.Div(id='output_row'),
    html.Br(),
    html.Br(),
    dbc.Row([
        dbc.Col(
            html.Div([
                dcc.Dropdown(options=DROPDOWN_OPTIONS,
                    placeholder="Select a taxon (level of orthology)",
                    value='4',
                    id='dropdown2',
                ),
                html.Div(id='dd2-output-container')
            ]),
            md=8,
            lg=6,
        ),
    ], justify='center'),

    dbc.Row([
        dbc.Col(
            html.Div([
                dcc.Store(id='blast-button-input-value', data=0),
                dbc.Button(
                    id="blast-button",
                    className="my-3",
                    color="success",
                ),
                dbc.Collapse(
                    dbc.Card(dbc.CardBody([
                        dbc.FormGroup([
                            dbc.Label("EValue", html_for="evalue"),
                            dbc.Select(
                                id="evalue",
                                options=[
                                    {"label": "10⁻⁵", "value": "-5"},
                                    {"label": "10⁻⁶", "value": "-6"},
                                    {"label": "10⁻⁷", "value": "-7"},
                                    {"label": "10⁻⁸", "value": "-8"},
                                ],
                                value="-5",
                            ),
                        ]),
                        dbc.FormGroup([
                            dbc.Label("Pident", html_for="pident-input-group"),
                            dbc.InputGroup(
                                [
                                    dbc.Input(id="pident-input"),
                                    dbc.InputGroupAddon("%", addon_type="append"),
                                ],
                                id="pident-input-group"
                            ),
                            dcc.Slider(id="pident-slider", min=0, max=100, step=0.5),
                        ]),
                        dcc.Store(id='pident-input-val', data=70),
                        dcc.Store(id='pident-output-val'),
                        dbc.Alert(
                            "Incorrect value!",
                            id="wrong-input-2",
                            is_open=False,
                            color="danger",
                        ),
                    ])),
                    id="blast-options",
                ),
            ]),
            md=8,
            lg=6,

        ),
    ], justify='center'),
    html.Br(),
    dbc.Row(
        dbc.Col(
            html.Button(id='submit-button2', type='submit', disabled=True, children='Go'),
            md=8,
            lg=6,

        ),
    justify='center'),
])


def dashboard(task_id):
    return html.Div([
        dcc.Store(id='task_id', data=task_id),
        dcc.Store(id='input1_version', data=0),
        dcc.Store(id='input1_refresh', data=0),
        dcc.Interval(
            id='progress_updater',
            interval=500, # in milliseconds
            disabled=True,
        ),
        body,
        html.Br(),
        html.Br(),
        og_from_input,
        dcc.Store(id='input2_refresh', data=0),
        dcc.Store(id='input2_version', data=0),

        dcc.Store(id='vis_version', data=0),
        dbc.Row(
            dbc.Col(
                id='vis_progress_container',
                md=8, lg=6,
            ),
            justify='center'
        ),

        dcc.Store(id='heatmap_version', data=0),
        dbc.Row(
            dbc.Col(
                id='heatmap_progress_container',
                md=8, lg=6,
            ),
            justify='center'
        ),
        dbc.Row(
            dbc.Col(
                id='heatmap_container',
                className="text-center",
            ),
            className="mx-4",
        ),

        dcc.Store(id='tree_version', data=0),
        dcc.Store(id='blast_version', data=0),
        dbc.Row(
            dbc.Col(
                id='tree_progress_container',
                md=8, lg=6,
            ),
            justify='center'
        ),
        dbc.Row(
            dbc.Col(
                id='tree_container',
                className="mx-5 mt-3",
            )
        ),

        html.Br(),
        html.Br(),
        # dcc.Link('Navigate to "Images"', href='/reports'),
    ])

reports = html.Div([
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
    ]),
    html.Div([
        # dcc.Dropdown(
        #     id='image-dropdown',
        #     options=[{'label': i, 'value': i} for i in list_of_images],
        #     value=list_of_images[0]
        # ),
        # html.Img(id='image')
    ])
])


blast = html.Div([
    body,
    html.Div(id='1'),
    html.Br(),
    html.Br(),
    html.P("The user can submit the query in the front page by either listing the Uniprot identifiers in the input field or by uploading .txt file. Taxonomic orthology levels include Eukaryota, Metazoa, Viridiplantae, Vertebrata, Aves, Actinopterygii, Fungi, Protista. For large taxonomic groups there is an option to continue with a compact set of species with a good quality of genome assembly, or with a full set of species from OrthoDB that may provide better resolution for conservation patterns (for example, the choice between 120 or 1100 species in Metazoa). After entering the query, a table of information related to each orthogroup is loaded. It collates query protein names with OrthoDB orthogroups identifiers, it also contains some other information about orthogroups already described in the previous section. The user can choose clades for which to display the correlation matrix and the presence heatmap with phylogenetic tree. Blast search can be performed to complement OrthoDB presence data. The user can change the default parameters for blastp search: sequence identity and E-value threshold."),
    html.Br(),
    html.P("The graphic representation of the results is a correlation matrix: the colors on the matrix reflect the values of the Pearson correlation coefficient, on both axes a color bar is added corresponding to the percentage of homologs presence in species: a high percentage corresponds to black, a low one is colored bright red. On the bottom of the page presence heatmap is constructed (). The columns show the orthogroups, with the same name as the query protein name. Rows of the heatmap show the eukaryotic genomes, major taxa on the species tree are labeled with different colors.  The front page also includes the link to a brief tutorial on using the tool."),
    html.Br(),
])


index = html.Div([
    navbar,
    dcc.Location(id='location', refresh=False),
    dbc.Container(
        id='page-content',
        fluid=True,
    )
])
