import json

from dash import (
  dcc,
  html,
  dash_table,
)
import dash_bootstrap_components as dbc

SHOW = {}
HIDE = {"display": "none"}

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
  dbc.NavItem(dbc.NavLink("Help/About", href="/about")),
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

body = html.Div(
    [
        dbc.Row([
            dbc.Col([
                html.H2("OrthoQuantum v1.0", style={"white-space": "nowrap"}),
            ], md=4, lg=3),
            dbc.Col([
                html.Hr(style={
                    "margin-top": "2rem",
                    "margin-bottom": "0",
                }),
                ], md=4, lg=3, className="d-none d-md-block"),
            ],
            justify='center',
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.P("""Download presence and study orthology group presence.
                                Use UniProt Accesion Codes of your proteins to create a list with corresponding
                                Orthology groups"""),
                        dbc.InputGroup([
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
                            className="input-group-text important-btn-secondary mr-2 mt-2", id="tutorial-checkbox-div"),
                            dbc.Button("Open demo data", id="demo-btn", color="secondary", className="mt-2"),
                            dbc.Tooltip(
                                "Information would be displayed while hovering over an element",
                                # id="tooltip-edit-title",
                                target="tutorial-checkbox-div",
                                placement="bottom"
                            ),
                        ]),
                    ],
                    md=4,
                    lg=3,
                ),
                html.Br(),
                html.Br(),
                dbc.Col([
                        html.P("To perform a query:"),
                        html.P(html.Ol([
                            html.Li("Select clades for which to display the correlation matrix and the phylogenetic profile"),
                            html.Li("Input a list of query genes. Choose organism scientific name or NCBI taxid to convert gene names into corresponding Uniprot IDs."),
                            html.Li("To perform BLAST search click on the ‘Enable BLAST’ button. The default parameters for blastp search (sequence identity and E-value threshold) can be modified."),
                        ])),
                        html.P("""Click "Submit" to see your results."""),
                    ],
                    md=4,
                    lg=3,
                ),
            ],
            justify='center',
        )
    ],
    className="mt-4",
)

og_from_input = html.Div(children=[
    dbc.Row([
      dbc.Col([
        html.H2("OrthoQuantum v1.0", style={"white-space": "nowrap"}),
      ], md=4, lg=3),
      dbc.Col([
        html.Hr(style={
          "margin-top": "2rem",
          "margin-bottom": "0",
        }),
        ], md=4, lg=3, className="d-none d-md-block"),
      ],
      justify='center',
    ),
    dbc.Row(
      [
        dbc.Col(
          [
            html.P("""Download presence and study orthology group presence.
                Use UniProt Accesion Codes of your proteins to create a list with corresponding
                Orthology groups"""),
            dbc.InputGroup([
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
              className="input-group-text important-btn-secondary mr-2 mt-2", id="tutorial-checkbox-div"),
              dbc.Button("Open demo data", id="demo-btn", color="secondary", className="mt-2"),
              dbc.Tooltip(
                "Information would be displayed while hovering over an element",
                # id="tooltip-edit-title",
                target="tutorial-checkbox-div",
                placement="bottom"
              ),
            ]),
          ],
          md=4,
          lg=3,
        ),
        html.Br(),
        html.Br(),
        dbc.Col([
            html.P("""Input protein IDs in the textarea and select current taxonomy (level of orthology)"""),
          ],
          md=4,
          lg=3,
        ),
      ],
      justify='center',
    )
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
        dcc.Store(id='uniprotAC_update', data=None),
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
          html.Div([
            dbc.Button(
              id="blast-button",
              className="my-3",
              color="success",
              children="Enable BLAST",
              outline=True,
            ),
            dbc.InputGroup(
              [
                dbc.InputGroupAddon("Max proteins on tree", addon_type="prepend"),
                dbc.Input(value="800", id="max-proteins", min="1", type="number"),
              ],
              className="float-right ml-auto",
              id="max-prot-group"
            ),
            dbc.Tooltip(
              "TKTKTK", # TODO
              id="tooltip-max-prot-group",
              target="max-prot-group",
              # placement="right",
              className="d-none"
            ),
          ],
          className="form-inline"),

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
                dbc.Input(
                  id="evalue",
                  value="1e-5",
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
                id="wrong-input-msg",
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
      dbc.Progress(
        html.Span(
          className="justify-content-center d-flex position-absolute w-100",
          style={"color": "black"},
          id="table_progress_text",
        ),
        id="table_progress_bar",
        style={"height": "30px"},
      ),
      md=8, lg=6,
    ),
    justify='center',
    id='table_progress_container',
    className="mb-3",
    style=HIDE,
  ),

  dbc.Row(
    dbc.Col(
      [
        html.Div(
          dash_table.DataTable(
            filter_action="native",
            page_size=40,
            id="data_table",
          ),
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
    style=HIDE,
    id="table_container",
  ),
])


def dashboard(task_id):
  return html.Div([
    dcc.Store(id='task_id', data=task_id),
    dcc.Store(id='connection_id', data=None),
    dcc.Store(id='version', data=None),
    dcc.Store(id='force_update', data=0),
    dcc.Interval(
      id='progress_updater',
      interval=500, # in milliseconds
      disabled=True,
    ),
    body,
    html.Br(),
    html.Br(),

    dcc.Store(id='request_title_update', data=""),
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

    dbc.Row(
      dbc.Col(
        dbc.Progress(
          html.Span(
            className="justify-content-center d-flex position-absolute w-100",
            style={"color": "black"},
            id="vis_progress_text",
          ),
          id="vis_progress_bar",
          style={"height": "30px"},
        ),
        md=8, lg=6,
      ),
      justify='center',
      id='vis_progress_container',
      style=HIDE,
    ),

    html.Div(
      [
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
          className='mt-5 mb-3'
        ),

        dbc.Row(
          dbc.Col(
            dbc.Progress(
              html.Span(
                className="justify-content-center d-flex position-absolute w-100",
                style={"color": "black"},
                id="heatmap_progress_text",
              ),
              id="heatmap_progress_bar",
              style={"height": "30px"},
            ),
            md=8, lg=6,
          ),
          justify='center',
          id='heatmap_progress_container',
          style=HIDE,
        ),
      ],
      id='heatmap_header',
      style=HIDE,
    ),
    html.Div(
      [
        dbc.Row(
          [
            dbc.Col(
              html.A(
                html.Img(
                  id="heatmap_img",
                  style={
                    'width': '100%',
                    'max-width': '1100px',
                  },
                  className="mx-auto",
                ),
                target="_blank",
                className="mx-auto",
                id="heatmap_link",
              ),
              className="text-center",
              md=6,
            ),
            dbc.Col(
              html.Div(
                dash_table.DataTable(
                  filter_action="native",
                  page_size=20,
                  id="corr_table",
                ),
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
      ],
      id='heatmap_container',
      style=HIDE,
    ),

    html.Div(
      [
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
          className='mt-5 mb-0'
        ),
        dbc.Row(
          dbc.Col(
            dbc.Progress(
              html.Span(
                className="justify-content-center d-flex position-absolute w-100",
                style={"color": "black"},
                id="tree_progress_text",
              ),
              id="tree_progress_bar",
              style={"height": "30px"},
            ),
            md=8, lg=6,
            className="mt-3"
          ),
          justify='center',
          id='tree_progress_container',
          style=HIDE,
        ),
      ],
      id="tree_header",
      style=HIDE,
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

def sized_img(img_src, href=None):
    if href is None:
        href = img_src
    return html.A(
            html.Img(
                src=img_src,
                style={
                    'width': '100%',
                    'max-width': '1100px',
                },
                className="mx-auto",
            ),
            href=href,
            target="_blank",
            className="mx-auto",
        )



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



def about(app):
    items = [
        html.H3("About", className="mb-3", ),
        html.P(
            [
                html.I("OrthoQuantum"),
                html.Span("""is a web-based tool for visualizing and studying phylogenetic presence/absence patterns of proteins and corresponding orthologous groups."""),
            ],
        ),
        html.P("""OrthoQuantum allows the user to submit protein queries, inspect the output in graphic format and download the output in .csv format. The tool visualizes phylogenetic profiles utilizing a set of databases with orthology predictions.  The webserver mainly relies on orthology predictions from the OrthoDB database, which  is leading in coverage of eukaryotic species, with 1,300 species that have a complete or nearly complete genome assembly and 37 million genes/proteins in the most recent update. Clustering of homologous sequences in OrthoDB occurs at the specified taxonomic level.  Multiple researchers can easily access the tool, which can display data from the set of over 1000 fully sequenced eukaryotic genomes and predicted orthologs at any given time.
        """),
        html.P("""A BLAST search can be performed to complement the orthology data. The user can submit the query in the front page by listing the UniProt identifiers or gene IDs in the input field."""),
        sized_img(app.get_asset_url('tutorial/1.png')),

        html.H3("How to run a basic job", className="mb-3"),
        html.P(html.U("To perform a query:")),
        html.P(html.Ol([
            html.Li("Select clades for which to display the correlation matrix and the phylogenetic profile"),
            html.Li("Input a list of query genes. Choose organism scientific name or NCBI taxid to convert gene names into corresponding Uniprot IDs."),
            html.Li("To perform BLAST search click on the ‘Enable BLAST’ button. The default parameters for blastp search (sequence identity and E-value threshold) can be modified."),
        ])),


        html.P("""Click "Submit" to see your results."""),
        html.P("""For brief descriptions, you can hover your mouse on fields to see the tooltip info messages."""),
        html.H3("Input query details", className="mb-3"),
        html.H5("""Step 1. Selection of Target Species"""),
        dbc.Row([
            dbc.Col(sized_img(app.get_asset_url('tutorial/2.png')), sm=6),
            dbc.Col(sized_img(app.get_asset_url('tutorial/3.png')), sm=6),
        ]),
        html.P("""Available eukaryotic species are divided into taxonomic categories based on levels of orthology in OrthoDB: Eukaryota, Metazoa, Viridiplantae, Vertebrata, Aves, Actinopterygii, Fungi, Protista. Users can select sets of target species by using the series of presented drop down menus. For large taxonomic groups there is an option to continue with a compact set of species with a good quality of genome assembly, or with a full set of species from OrthoDB that may provide better resolution for conservation patterns (for example, the choice between 120 or 1100 species in Eukaryota). Once the target species have been selected, the user can input the sequence IDs."""),

        html.H5("Step 2. Query Sequences"),
        sized_img(app.get_asset_url('tutorial/4.png')),
        html.P("""The user is presented with a window, with radio buttons to indicate the sources (species) of the query sequences and two text boxes in which to enter sequence IDs: """),
        html.Ul([
            html.Li("Gene Symbol: official gene names are converted into UniprotKB accesions by clicking ‘Find Uniprot ACs’. "),
            html.Li("GeIf the user has Uniprot ACs  (the UniProtKB accession number) they can be pasted straightaway in the text box on the right."),
        ]),
        html.P("""Note there is an upper limit of 1000 query sequences for compact Eukaryota set and 100 species for full (all 1100 species available on OrthoDB)."""),

        html.H5("Step 3. Selection of BLAST Options"),
        html.P("""For orthogroups that have missing elements, a search for potential homologs was conducted against the NCBI nonredundant protein sequence database (nr) using the blastp algorithm. In this step, users can choose two parameters, the Similarity Metric and the Clustering Method."""),
        sized_img(app.get_asset_url('tutorial/5.png')),
        html.P("""The Similarity Metric option refers to how similarity (or alternatively, distance) between phylogenetic profiles is measured. Cluster3.0 features eight options. The basic idea of hierarchical clustering is to assemble a set of items into a tree, where items are joined by very short branches if they are very similar to each other, and by increasingly longer branches as their similarity decreases (Eisen, et al., 1998) . Cluster3.0 performs four types of binary, agglomerative, hierarchical clustering: centroid, single, complete or average linkages. Different methods refer to different ways to join branches and can result in different clustered outputs. More details of clustering options can be found in (Eisen, et al., 1998) ."""),

        html.H5("Step 4. Execute the Query"),
        html.P("""By clicking the 'Search' button, users then proceed to the visualization page. The query can be cancelled by clicking 'Cancel'."""),

        html.H3("Results: Phylogenetic Profiles Visualization", className="mb-3"),
        html.P("""At this stage users are presented with a visualization of their results which features an interactive heatmap of orthology relationships. The graphic representation of the results is a correlation matrix: the colors on the matrix reflect the values of the Pearson correlation coefficient, on both axes a color bar is added corresponding to the percentage of homologs presence in species: a high percentage corresponds to black, a low one is colored bright red."""),
        sized_img(app.get_asset_url('tutorial/6.png')),
        html.P("""On the bottom of the page phylogenetic profile heatmap is constructed. The columns show the orthogroups, with the same name as the query protein name. The order of query sequences is defined by the hierarchical clustering. Rows of the heatmap show the eukaryotic genomes, major taxa on the species tree are labeled with different colors. Mousing over an individual tile in the heatmap reveals the query species, gene names of both the query and orthologous genes."""),
        sized_img(app.get_asset_url('tutorial/7.png')),
        sized_img(app.get_asset_url('tutorial/8.png')),

        html.P("""The heatmap figure can be downloaded as a PNG file by selecting 'Download Image' button. In addition, ‘Download csv’ button provides links to download data associated with the heatmap. """),
        html.P("""Caveats"""),
        html.P("""It should be noted that there are a number of caveats associated with orthology detection (Kuzniar, et al., 2008; Rano-Rubio et al. 2009). Firstly, in the absence of detailed phylogenetic analyses, domain gains, losses and shuffling events can significantly complicate orthology assignments. Secondly, horizontal gene transfer introduces an additional problem of xenologs which can lead to confounding outcomes. Thirdly, the quality and coverage of genome annotation varies significantly between genome projects. Genomes or lower quality or with lower fold coverage may be associated with incomplete proteomes, giving rise to apparently missing orthologs. Here we have attempted to use published genomes that provide a good compromise between phylogenetic coverage and what we consider are useful genome assemblies. As more genomes are sequenced, there is an increasing recognition for a set of 'industry' standards to be defined (Chain et al., 2009)."""),
        html.H3("References", className="mb-3"),
        html.P([
            """Chain PS et al Genome project standards in a new era of sequencing. Science. 2009 Oct 9;326(5950):236-7)""", html.Br(),
            """Eisen, M.B., et al. (1998) Cluster analysis and display of genome-wide expression patterns, Proc Natl Acad Sci U S A, 95, 14863-14868.""", html.Br(),
            """Hulsen, T., et al. (2009) PhyloPat: an updated version of the phylogenetic pattern database contains gene neighborhood, Nucleic Acids Res, 37, D731-737.""", html.Br(),
            """Kuzniar, A., et al. (2008) The quest for orthologs: finding the corresponding gene across genomes, Trends Genet, 24, 539-551.""", html.Br(),
            """Pellegrini, M., et al. (1999) Assigning protein functions by comparative genome analysis: protein phylogenetic profiles, Proceedings of the National Academy of Sciences of the United States of America, 96, 4285-4288.""", html.Br(),
            """Ruano-Rubio, V., Poch, O. and Thompson, J. (2009) Comparison of eukaryotic phylogenetic profiling approaches using species tree aware methods, BMC bioinformatics, 10, 383.""", html.Br(),
            """Schneider, A., Dessimoz, C. and Gonnet, GH. (2007): OMA Browser - Exploring Orthologous Relations across 352 Complete Genomes, Bioinformatics 23(16), pages 2180-2182.""", html.Br(),
            """von Mering, C., et al. (2003) STRING: a database of predicted functional associations between proteins, Nucleic Acids Res, 31, 258 - 261.""",
        ]),
        html.P("""Quick Links to Databases"""),
        html.Ul([
            html.Li(html.A("OrthoDB", href="http://www.utoronto.ca/")),
            html.Li(html.A("PANTHER", href="http://llama.mshri.on.ca/synergizer/translate/")),
            html.Li(html.A("NCBI", href="http://inparanoid.sbc.su.se/cgi-bin/index.cgi")),
        ]),
        # html.P(""""""),

        ###
        # html.P(
        #     "The user can submit the query in the front page by either listing the Uniprot identifiers in the input field or by uploading .txt file. Taxonomic orthology levels include Eukaryota, Metazoa, Viridiplantae, Vertebrata, Aves, Actinopterygii, Fungi, Protista. For large taxonomic groups there is an option to continue with a compact set of species with a good quality of genome assembly, or with a full set of species from OrthoDB that may provide better resolution for conservation patterns (for example, the choice between 120 or 1100 species in Metazoa). After entering the query, a table of information related to each orthogroup is loaded. It collates query protein names with OrthoDB orthogroups identifiers, it also contains some other information about orthogroups already described in the previous section. The user can choose clades for which to display the correlation matrix and the presence heatmap with phylogenetic tree. Blast search can be performed to complement OrthoDB presence data. The user can change the default parameters for blastp search: sequence identity and E-value threshold.",
        # ),
        # html.P(
        #     "The graphic representation of the results is a correlation matrix: the colors on the matrix reflect the values of the Pearson correlation coefficient, on both axes a color bar is added corresponding to the percentage of homologs presence in species: a high percentage corresponds to black, a low one is colored bright red. On the bottom of the page presence heatmap is constructed (). The columns show the orthogroups, with the same name as the query protein name. Rows of the heatmap show the eukaryotic genomes, major taxa on the species tree are labeled with different colors.  The front page also includes the link to a brief tutorial on using the tool."
        # ),
    ]
    # H3 h5
    counter = 1
    contents = html.Ul([], style={
        "padding-left": "20px",
    })
    i = 0
    while i < len(items):
        item = items[i]
        if not isinstance(item, (html.H3, html.H5)):
            i += 1
            continue
        # <a class="anchor" id="top"></a>
        _id = f"item_{counter}"
        counter+=1
        items.insert(i, html.A(className="anchor", id=_id))
        i += 2
        if isinstance(item, html.H5):
            if not isinstance(contents.children[-1], html.Ul):
                contents.children.append(html.Ul([]))
            arr = contents.children[-1].children
        else:
            arr = contents.children

        arr.append(
            html.Li(html.A(item.children, href=f"#{_id}"))
        )

    return dbc.Row(
        dbc.Col([
            html.H2("OrthoQuantum v1.0", className="text-center mt-5 mb-5"),
            dbc.Card(
                dbc.CardBody(contents),
                style={"width": "26rem"},
                className="mb-4",
            ),
            *items,
        ], md=8, lg=6),
        justify='center',
    )
