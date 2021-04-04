import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Blast", href="/blast")),
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

dashboard = html.Div([
    navbar,
    body,
    html.Br(),
    html.Br(),
    og_from_input,
    html.Div(id='output_div2'),
    dcc.Link('Navigate to "Images"', href='/reports'),
    # html.Img(src=r'C:\Users\nfsus\OneDrive\best_repository_ever\Dash_app\assets\images\Correlation.png')
])

reports = html.Div([
    navbar,
    dbc.Container(
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
    ),
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
    navbar,
    body,
    html.Div(id='1'),
])


index = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])