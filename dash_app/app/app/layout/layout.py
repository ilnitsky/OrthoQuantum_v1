import json
from dash_bootstrap_components._components.Button import Button

import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

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
    # dbc.DropdownMenu doesn't expose n_clicks to fetch the newest data
    # recreating their functionality manually
    html.Li([
            html.A(
                "My requests",
                className="nav-link dropdown-toggle",
                id="request_list_menu_item",
                role="button",
            ),
            dcc.Store(id='request_list_dropdown_shown', data=False),
            html.Div([
                    dbc.DropdownMenuItem(
                        "New request",
                        external_link=True, href=f"/",
                    ),
                    dbc.DropdownMenuItem(divider=True),
                    dbc.DropdownMenuItem("Loading...", disabled=True),
                ],
                id="request_list_dropdown",
                role="menu",
                tabIndex="-1",
                className="dropdown-menu dropdown-menu-right",
                style={"max-height": "80vh", "overflow-y": "scroll", "min-width": "300px"},
            ),
        ],
        className="nav-item dropdown"
    ),
]
if DEBUG:
    nav_children.insert(0, dbc.NavItem(dbc.NavLink("Flush Cache", id="flush-button")),)
    nav_children.insert(0, dbc.NavItem(
        [
            html.Div("X-LARGE (XL)", className="d-none d-xl-block font-weight-bold"),
            html.Div("LARGE (LG)", className="d-none d-lg-block d-xl-none font-weight-bold"),
            html.Div("MEDIUM (M)", className="d-none d-md-block d-lg-none font-weight-bold"),
            html.Div("SMALL (SM)", className="d-none d-sm-block d-md-none font-weight-bold"),
            html.Div("X-SMALL (Defaut)", className="d-block d-sm-none alert font-weight-bold"),
        ]

    ))


navbar = dbc.NavbarSimple(
    children=nav_children,
    brand="Home",
    brand_external_link=True,
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
                    dbc.InputGroup([
                        # dbc.Button("View tutorial", color="secondary", href="/blast"),
                        html.Div([
                            dbc.Checkbox(id="tutorial_checkbox"),
                            dbc.Label(
                                "Show tutorial",
                                html_for="tutorial_checkbox",
                                className="form-check-label",
                                style={"margin-left": "0.5em"},
                            ),
                        ],
                        # unfortunately bootstrap isn't cooperating here, forcing btn-secondary look with custom class
                        className="input-group-text important-btn-secondary", id="tutorial-checkbox-div"),
                        dbc.Button("Open demo data", id="demo-btn", color="secondary", className="ml-2",),
                        dbc.Tooltip(
                            "Information would be displayed while hovering over an element",
                            # id="tooltip-edit-title",
                            target="tutorial-checkbox-div",
                            placement="bottom"
                        ),
                    ]),
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
            dbc.Col([
                    html.Div(
                        dcc.Dropdown(
                            placeholder="Select a taxon (level of orthology)",
                            value='4', # vertebrata
                            id='tax-level-dropdown',
                            options=DROPDOWN_OPTIONS,
                        ),
                        id='tax-dropdown-container',
                    ),
                    dbc.Tooltip(
                        "Select level of orthology. Clustering of homologous sequences in OrthoDB occurs at the specified taxonomic level.",
                        id="tooltip-orthology",
                        target="tax-dropdown-container",
                        placement="right",
                        className="d-none"
                    ),
                ],
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
                dcc.Store(id='taxid_input_numeric', data=False),
                dcc.Store(id='prot-search-result', data=''),
                dcc.Interval(
                    id='prot_search_updater',
                    interval=500, # in milliseconds
                    disabled=True,
                ),
                dcc.Dropdown(
                    id='taxid_input',
                    placeholder="Select species/enter taxid",
                    className="mb-2"
                ),
                dcc.Textarea(id="prot-codes", placeholder='Gene of interest names', value='', rows=6, style={'width': '100%'}),
                dbc.Tooltip(
                    "Convert gene names to Uniprot IDs to perform search.",
                    id="tooltip-gene-search",
                    target="prot-codes",
                    placement="right",
                    className="d-none"
                ),
                dbc.Button(
                    id="search-prot-button",
                    color="primary",
                    children="Find Uniprot ACs ➜",
                    outline=True,
                    className="float-right",
                ),
            ]),
            md=4,
            lg=3,
        ),
        # html.Button("➜", style={}),
        # html.Div(dbc.Button("->")),
        dbc.Col(
            html.Div([
                dcc.Textarea(id='uniprotAC', placeholder='This app uses Uniprot AC (Accession Code): for example "Q91W36" ', value='', rows=10, style={'width': '100%'}),
            ]),
            md=4,
            lg=3,
        ),
    ], justify='center'),

    dbc.Row(
        [
            dbc.Col(
                html.Div([
                    dcc.Store(id='blast-button-input-value', data=0),
                    dbc.Button(
                        id="blast-button",
                        className="my-3",
                        color="success",
                        children="Enable BLAST",
                        outline=True,
                    ),
                    dbc.Tooltip(
                        "For orthogroups that have missing elements, an additional search for potential homologs will be conducted against the NCBI nr database  using the blastp algorithm. Percent identity and query coverage parameters can be changed.",
                        id="tooltip-blast-button",
                        target="blast-button",
                        placement="right",
                        className="d-none"
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
                            dcc.Store(id='pident-output-val', data=70),

                            dbc.FormGroup([
                                dbc.Label("Qcovs", html_for="qcovs-input-group"),
                                dbc.InputGroup(
                                    [
                                        dbc.Input(id="qcovs-input"),
                                        dbc.InputGroupAddon("%", addon_type="append"),
                                    ],
                                    id="qcovs-input-group"
                                ),
                                dcc.Slider(id="qcovs-slider", min=0, max=100, step=0.5),
                            ]),
                            dcc.Store(id='qcovs-input-val', data=70),
                            dcc.Store(id='qcovs-output-val', data=70),


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
        ],
        justify='center',
        className="mb-3"
    ),

    dbc.Row(
        dbc.Col(
            [
                dbc.Button(
                    id="submit-button",
                    color="primary",
                    children="Submit",
                    className=""
                ),
                dbc.Button(
                    id="cancel-button",
                    color="danger",
                    children="Cancel",
                    outline=True,
                    className="float-right d-none"
                ),
            ],
            md=8,
            lg=6,
        ),
        justify='center',
        className="mb-4",
    ),
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
            [
                html.Div(
                    id="table_container",
                    style={
                        "overflow-x": "scroll",
                    }
                ),
                dbc.Tooltip(
                    "Orthogroups information. To see the PANTHER subfamily annotation click on the name of protein/orthogroup.",
                    id="tooltip-table",
                    target="table_container",
                    placement="right",
                    className="d-none"
                ),
            ],
            md=8, lg=6,
        ),
        justify='center',
        className="mb-3",
    ),
])


def dashboard(task_id):
    return html.Div([
        dcc.Store(id='task_id', data=task_id),
        dcc.Store(id='input1_version', data=0),
        # desired version of a component, updated on submit and cancellation
        dcc.Store(id='table_version_target', data=0),
        dcc.Store(id='tree_version_target', data=0),
        dcc.Store(id='input1_refresh', data=0),
        dcc.Interval(
            id='progress_updater',
            interval=500, # in milliseconds
            disabled=True,
        ),
        body,
        html.Br(),
        html.Br(),

        dbc.Row(
            dbc.Col(
                [
                    html.A(
                        [
                            html.H1(
                                "",
                                className="text-center",
                                id="request-title",
                            ),
                            dbc.Tooltip(
                                "Click to edit",
                                id="tooltip-edit-title",
                                target="request-title",
                                placement="right",
                                className="d-none"
                            ),
                        ]
                        ,
                        id="edit-request-title",
                        role="button",
                        className="text-decoration-none"
                    ),
                    dbc.Input(
                        id="request-input",
                        className="d-none",
                        style={"text-align": "center"}
                    ),
                ],
                md=8, lg=6, className="mb-3",
            ),
            justify='center'
        ),

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
            [
                html.H3("Correlation matrix", id="corr_matrix_title"),
                dbc.Tooltip(
                    "The colors on the correlation matrix reflect the values of the Pearson correlation coefficient, on both axes a color bar is added corresponding to the percentage of homologs presence in species: a high percentage corresponds to black, a low one is colored bright red. The table contains sorted pairwise correlations.",
                    id="tooltip-heatmap",
                    target="corr_matrix_title",
                    placement="right",
                    className="d-none",
                ),
            ],
            justify='center',
            id="heatmap_title_row",
            style={'display': "none"},
            className='mt-5 mb-3'
        ),
        dbc.Row(
            dbc.Col(
                id='heatmap_progress_container',
                md=8, lg=6,
            ),
            justify='center'
        ),
        dbc.Row(
            [
                dbc.Col(
                    id='heatmap_container',
                    className="text-center",
                    md=6,
                ),
                dbc.Col(
                    html.Div(
                        id="corr_table_container",
                        className="pb-3",
                        style={
                            "overflow-x": "scroll",
                        },
                    ),
                    md=6,
                ),
            ],
            className="mx-4",
        ),

        dcc.Store(id='tree_version', data=0),
        dcc.Store(id='blast_version', data=0),
        dbc.Row(
            [
                html.H3("Phylogenetic profile plot", id="tree_title"),
                dbc.Tooltip(
                    "The columns show the orthogroups, with the same name as the query proteins. Rows of the heatmap show the eukaryotic genomes, major taxa on the species tree are labeled with different colors. To scale the graph use a mouse wheel (only  x axis -  Alt, only y axis - Ctrl).",
                    id="tooltip-tree",
                    target="tree_title",
                    placement="right",
                    className="d-none"
                ),
            ],
            justify='center',
            id="tree_title_row",
            style={'display': "none"},
            className='mt-5 mb-0'
        ),
        dbc.Row(
            dbc.Col(
                id='tree_progress_container',
                md=8, lg=6,
                className='mt-3'
            ),
            justify='center'
        ),
        dbc.Row(
            dbc.Col(
                id='blast_progress_container',
                md=8, lg=6,
                className='mt-3'
            ),
            justify='center'
        ),
        dbc.Row(
            dbc.Col(
                id='tree_container',
                className="mx-5 mt-3",
            )
        ),
        html.Div(
            [
                dbc.Row(
                    dbc.Col(
                        [
                            html.Div([
                                html.Span(
                                    "Show names:",
                                    className="align-top"
                                ),
                                html.Div(
                                    [
                                        dbc.Label([dbc.Checkbox(id="show_groups", className="form-check-input"), "Groups"], className="ml-4 form-check-label"),
                                        html.Br(),
                                        dbc.Label([dbc.Checkbox(id="show_species", className="form-check-input"), "Species"], className="ml-4 form-check-label"),

                                    ],
                                    className="align-top d-inline-block"
                                ),
                                dbc.Button("Rerender", id="rerenderSSR_button", className="ml-4 align-top")
                            ]),
                            dcc.Slider(id="svg_zoom", min=0, max=200, value=100, step=1, updatemode='drag'),
                            html.Span(
                                id="svg_zoom_text",
                                className="float-right"
                            ),                        ],

                        md=6, lg=4,
                        className="mt-2 mx-5",
                    ),
                ),
                dbc.Row(
                    dbc.Col(
                        [
                            html.Div(
                                html.Img(
                                    id="ssr_tree_img",
                                ),
                                style={
                                    "max-width": "100%",
                                    "max-height": "2000px",
                                    "overflow": "scroll",
                                },
                            ),
                        ],
                        className="mx-5 mt-3",
                    )
                ),
            ],
            id='ssr_tree_block',
            style={"display": "none"}
        ),
        html.Br(),
        html.Br(),

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
    html.Div(
        id="location-refresh-cont",
    ),
    dcc.Store(id='tutorial_enabled', data=True, storage_type="local"),
    dbc.Container(
        id='page-content',
        fluid=True,
    )
])

def prottree(prot_id):
    return html.Div([
        dcc.Store(id='prot_id', data=prot_id),
        dcc.Interval(
            id='prottree_progress_updater',
            interval=500, # in milliseconds
            disabled=False,
        ),
        dbc.Row(
            dbc.Col(
                id='prottree_container',
                className="mx-5 mt-3",
            )
        ),
    ])

def csvdownload(task_id):
    return html.Div([
        dcc.Store(id='task_id', data=task_id),
        dcc.Store(id='csvdownload_done', data=False),
        dcc.Location(id="csv_redirect", refresh=True),
        dcc.Interval(
            id='csvdownload_progress_updater',
            interval=500, # in milliseconds
            disabled=False,
        ),
        dbc.Row(
            dbc.Col(
                id='csvdownload_container',
                className="mx-5 mt-3",
            )
        ),
    ])