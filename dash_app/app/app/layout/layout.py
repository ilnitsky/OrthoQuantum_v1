import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

navbar = dbc.NavbarSimple(
    children=[
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
    ],
    brand="Home",
    brand_href="/dashboard",
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
                        value='Vertebrata',
                        id='dropdown',
                        options=[
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
                    ),
                    html.Div(id='dd-output-container')
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
    html.Div(id='output_row'),
    html.Br(),
    html.Br(),
    dbc.Row([
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
                    id='dropdown2',
                ),
                html.Div(id='dd2-output-container')
            ]),
            md=8,
            lg=6,

        ),
    ], justify='center'),
    html.Br(),
    dbc.Row([
        dbc.Col(
            html.Button(id='submit-button2', type='submit', disabled=True, children='Go'),
            md=8,
            lg=6,

        ),
    ], justify='center'),
])


def dashboard(task_id):
    return html.Div([
        dcc.Store(id='task_id', data=task_id),
        dcc.Store(id='input_version', data=0),
        dcc.Interval(
            id='table-progress-updater',
            interval=500, # in milliseconds
            disabled=True,
        ),
        body,
        html.Br(),
        html.Br(),
        og_from_input,
        dcc.Store(id='input2-version', data=0),

        dcc.Interval(
            id='progress-updater-2',
            interval=500, # in milliseconds
            disabled=True,
        ),
        html.Div(id='sparql-output-container'),
        dcc.Link('Navigate to "Images"', href='/reports'),
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
