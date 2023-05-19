from phydthree_component import PhydthreeComponent

import dbc
import dcc
import html
import dash_table

SHOW = {}
HIDE = {"display": "none"}

DEBUG = False

DROPDOWN_OPTIONS = [
  {
    'label': "SomeLBL",
    'value': 1,
  },
  {
    'label': "SomeLBL2",
    'value': 2,
  }
#   for name, id in json.loads(db.get("/availible_levels")).items()
]

EXTRA_TABLE_COLUMNS = [
  {
    "name": name,
    "id": i,
  }
  for i, name in enumerate((
    'Query',
    'OrthoDB id',
    'Gene Name',
    'Description',
    'Gene Count',
    'Present in # species',
  ))
]
EXTRA_TABLE_COLUMNS[0]['type'] = 'text'
EXTRA_TABLE_COLUMNS[0]['presentation'] = 'markdown'
EXTRA_TABLE_COLUMNS[1]['type'] = 'text'
EXTRA_TABLE_COLUMNS[1]['presentation'] = 'markdown'

TABLE_COLUMNS = [
  {
    "name": name,
    "id": i,
  }
  for i, name in enumerate((
    "OG label",
    "Gene Names",
    "Description",
    "Level",
    "EvolRate",
    "TotalGenesCount",
    "MultiCopyCount",
    "SingleCopyCount",
    "Present in # species",
    # "medianExonsCount", "stddevExonsCount",
    "MedianProteinLength",
    "StddevProteinLength"
  ))
]
TABLE_COLUMNS[0]['type'] = 'text'
TABLE_COLUMNS[0]['presentation'] = 'markdown'
TABLE_COLUMNS[1]['type'] = 'text'
TABLE_COLUMNS[1]['presentation'] = 'markdown'


nav_children = [
  dbc.NavItem(dbc.NavLink("Help/About", href="/about")),
  # dbc.DropdownMenu doesn't expose n_clicks to fetch the newest data
  # recreating their functionality manually
  html.Li([
      html.A(
        "My queries",
        className="nav-link dropdown-toggle",
        id="request_list_menu_item",
        role="button",
      ),
      dcc.Store(id='request_list_dropdown_shown', data=False),
      html.Div([
          dbc.DropdownMenuItem(
            "New query",
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
            ], md=5, lg=4),
            dbc.Col([
                html.Hr(style={
                    "margin-top": "2rem",
                    "margin-bottom": "0",
                }),
                ], md=5, lg=4, className="d-none d-md-block"),
            ],
            justify='center',
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.P("""OrthoQuantum is a web-based tool for visualizing and studying phylogenetic presence/absence patterns of proteins and corresponding orthologous groups."""),
                        html.P("""OrthoQuantum allows the user to submit protein queries, inspect the output in graphic format and download the output in .csv format. The tool visualizes phylogenetic profiles utilizing a set of databases with orthology predictions."""),
                        html.P("""A BLAST search can be performed to complement the orthology data."""),

                        dbc.InputGroup([
                            html.Div([
                                dbc.Checkbox(id="tutorial_checkbox"),
                                dbc.Label(
                                    "Show description on hover",
                                    html_for="tutorial_checkbox",
                                    className="form-check-label",
                                    style={"margin-left": "0.5em"},
                                ),
                            ],
                            # unfortunately bootstrap isn't cooperating here, forcing btn-secondary look with custom class
                            className="input-group-text important-btn-secondary mr-2 mt-2", id="tutorial-checkbox-div"),
                            dbc.Button("Load demo data", id="demo-btn", color="secondary", className="mt-2"),
                            dbc.Tooltip(
                                "Information would be displayed while hovering over an element",
                                # id="tooltip-edit-title",
                                target="tutorial-checkbox-div",
                                placement="bottom"
                            ),
                        ]),
                    ],
                    md=5,
                    lg=4,
                ),
                html.Br(),
                html.Br(),
                dbc.Col([
                        html.P("To perform a query:"),
                        html.Ol([
                            html.Li("Select clades for which to display the correlation matrix and the phylogenetic profile. Choose organism scientific name or NCBI taxid."),
                            html.Li("Input a list of query genes. Please use line breaks as a delimiter. OrthoQuantum accepts identifiers of proteins and genes, such as NCBI RefSeq, Genbank, UniProt ACs.  InterPro, KEGG, OrthoDB orthogroup IDs also can be used."),
                            html.Li("To perform BLAST search click on the ‘Enable BLAST’ button. The default parameters for BlastP search (E-value threshold, sequence identity, and query coverage) can be modified."),
                        ]),
                        html.P("""Click "Submit" to see your results."""),
                    ],
                    md=5,
                    lg=4,
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
      ], md=5, lg=4),
      dbc.Col([
        html.Hr(style={
          "margin-top": "2rem",
          "margin-bottom": "0",
        }),
        ], md=5, lg=4, className="d-none d-md-block"),
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
                  "Show description on hover",
                  html_for="tutorial_checkbox",
                  className="form-check-label",
                  style={"margin-left": "0.5em"},
                ),
              ],
              # unfortunately bootstrap isn't cooperating here, forcing btn-secondary look with custom class
              className="input-group-text important-btn-secondary mr-2 mt-2", id="tutorial-checkbox-div"),
              dbc.Button("Load demo data", id="demo-btn", color="secondary", className="mt-2"),
              dbc.Tooltip(
                "Information would be displayed while hovering over an element",
                # id="tooltip-edit-title",
                target="tutorial-checkbox-div",
                placement="bottom"
              ),
            ]),
          ],
          md=5,
          lg=4,
        ),
        html.Br(),
        html.Br(),
        dbc.Col([
            html.P("""Input protein IDs in the textarea and select current taxonomy (level of orthology)"""),
          ],
          md=5,
          lg=4,
        ),
      ],
      justify='center',
    )
  ],
  className="mt-4",
)

def progress_bar(name, md=10, lg=8, height="30px"):
  return dbc.Row(
    dbc.Col([
      html.Span(
          className="d-flex justify-content-center align-items-center position-absolute w-100",
          style={"color": "black", "height": height, "font-size": "0.9rem"},
          id=f"{name}_progress_text",
        ),
      dbc.Progress(
        id=f"{name}_progress_bar",
        style={"height": height},
      ),
      ],
      md=md, lg=lg,
    ),
    justify='center',
    id=f"{name}_progress_container",
    className="mb-3 mt-3",
    style=HIDE,
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
          dcc.Store(id='taxid_input_numeric', data=False),
          dcc.Store(id='taxid_input_from_srv', data=None),
          dcc.Dropdown(
            id='taxid_input',
            placeholder="Select species/enter taxid",
            className="mt-2"
          ),
        ],
        md=10,
        lg=8,
      ),
    ],
    justify='center',
  ),
  html.Br(),
  dbc.Row([
    dbc.Col(
      html.Div([
        dcc.Store(id='prot-search-result', data=''),
        dcc.Textarea(id="prot-codes", placeholder='Gene of interest names', value='', rows=6, style={'width': '100%'}),
        dbc.Tooltip(
          "Convert gene names to Uniprot IDs to perform search.",
          id="tooltip-gene-search",
          target="prot-codes",
          placement="right",
          className="d-none"
        ),
      ]),
      md=5,
      lg=4,
      style=HIDE,
    ),
    dbc.Col([
        html.Div([
          dcc.Store(id='uniprotAC_update', data=None),
          dcc.Textarea(id='uniprotAC', placeholder='Input a list of query gene/protein/orthogroup IDs or keywords ...', value='', rows=10, style={'width': '100%'}),
        ]),
      ],
      md=10,
      lg=8,
    ),
  ], justify='center'),

  progress_bar("search"),

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
                dbc.InputGroupAddon("Max proteins on the tree", addon_type="prepend"),
                dbc.Input(value="600", id="max-proteins", min="5", type="number"),
              ],
              className="float-right ml-auto",
              id="max-prot-group"
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
                dbc.Label("E-value threshold", html_for="evalue"),
                dbc.Input(
                  id="evalue",
                  value="1e-5",
                ),
              ]),
              dbc.FormGroup([
                dbc.Label("Sequence identity", html_for="pident-input-group"),
                dbc.InputGroup(
                  [
                    dbc.Input(id="pident-input"),
                    dbc.InputGroupAddon("%", addon_type="append"),
                  ],
                  id="pident-input-group"
                ),
                dcc.Slider(id="pident-slider", min=0, max=100, step=0.5, marks=None),
              ]),
              dcc.Store(id='pident-input-val', data=70),
              dcc.Store(id='pident-output-val', data=70),

              dbc.FormGroup([
                dbc.Label("Query coverage", html_for="qcovs-input-group"),
                dbc.InputGroup(
                  [
                    dbc.Input(id="qcovs-input"),
                    dbc.InputGroupAddon("%", addon_type="append"),
                  ],
                  id="qcovs-input-group"
                ),
                dcc.Slider(id="qcovs-slider", min=0, max=100, step=0.5, marks=None),
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
        md=10,
        lg=8,
      ),
    ],
    justify='center',
    className="mb-3"
  ),

  dbc.Row(
    dbc.Col(
      dbc.Alert(
        id="missing_prot_alert",
        is_open=False,
        className="alert-warning",
      ),
      md=10, lg=8,
    ),
    justify='center',
  ),

  dbc.Row(
    dbc.Col(
      dbc.Collapse(
        dbc.Card(dbc.CardBody([
          dbc.Alert(
            children="Some query strings yielded multiple matching orthogroups. Select the ones you are interested in and re-submit.",
            is_open=True,
            className="alert-info",
          ),
          html.Div(
            dash_table.DataTable(
              page_size=40,
              row_selectable="multi",
              columns=EXTRA_TABLE_COLUMNS,
              id="extra_data_table",
            ),
            style={
              "overflow-x": "scroll",
            }
          ),
          dbc.Tooltip(
            "Choose orthogroups to investigate further",
            id="tooltip-extra-table",
            target="extra_table_container",
            placement="right",
            className="d-none"
          ),
        ])),
        id="extra_table_container",
      ),
      md=10, lg=8,
    ),
    justify='center',
    className="mb-3",
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
        dbc.Checkbox(
          id="extra_auto_select",
          className="ml-3"
        ),
        dbc.Label(
          "Automatically select the most relevant orthogroup",
          html_for="extra_auto_select",
          className="ml-1"
        ),
        dbc.Button(
          id="cancel-button",
          color="danger",
          children="Cancel",
          outline=True,
          className="float-right d-none"
        ),
      ],
      md=10,
      lg=8,
    ),
    justify='center',
    className="mb-4",
  ),
  progress_bar("table"),

  dbc.Row(
    dbc.Col(
      [
        html.Div(
          dash_table.DataTable(
            filter_action="native",
            sort_action='native',
            page_size=40,
            id="data_table",
            columns=TABLE_COLUMNS,
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
      md=10, lg=8,
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
    dcc.Store(id='force_update_until', data=0),
    dcc.Store(id='version', data=None),
    dcc.Store(id='data_submit_error', data=False),

    dcc.Store(id='trigger_csv_download', data=0),
    dcc.Store(id='trigger_csv_download_2', data=0),
    dcc.Store(id='trigger_csv_download_refresh', data=0),
    html.A(id='csvdownload_done_link', href=f'/files/{task_id}/tree.csv', download='tree.csv', className="d-none"),

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
                "Loading...",
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
        md=10, lg=8, className="mb-3",
      ),
      justify='center'
    ),

    og_from_input,
    dbc.Row(
      dbc.Col(
        dbc.Alert(
          id="missing_uniprot_alert",
          is_open=False,
          className="alert-warning",
        ),
        md=10, lg=8,
      ),
      justify='center',
    ),
    progress_bar("vis"),

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
        progress_bar("heatmap"),
      ],
      id='heatmap_header',
      style=HIDE,
    ),
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
          lg=4,
        ),
        dbc.Col(
          [
            html.Div(
              [
                dbc.Button("Options", style={"visibility": "hidden"}, className="d-none d-xl-block"), # for InputGroup to be centered
                dbc.InputGroup([
                  dbc.InputGroupAddon(dbc.Button("&lt;", id="curr_page_decr"), addon_type='prepend'),
                  dbc.Input(inputMode='numeric', value="1", id="curr_page", debounce=True),
                  dbc.InputGroupAddon("/Loading...", addon_type='append', id="total_pages"),
                  dbc.InputGroupAddon(dbc.Button("&gt;", id="curr_page_incr"), addon_type='append'),
                ], style={"width": "14em"}),
                dbc.Button("Options", id="corr_table_options_show"),
              ],
              className="d-flex flex-row justify-content-between mb-2",
            ),
            dbc.Collapse(
              dbc.Card(dbc.CardBody([
                dbc.Row([
                  dbc.Col(
                    [
                      html.Div([
                        dbc.Input(inputMode='numeric', value="0.0", className="d-inline-block", style={"width": "4em"}, id="min_quantile", debounce=True),
                        html.Span("≤\N{NBSP}quantile\N{NBSP}≤", className="p-2 input-group-text d-inline-block"),
                        dbc.Input(inputMode='numeric', value="1.0", className="d-inline-block", style={"width": "4em"}, id="max_quantile", debounce=True),
                      ], className="mb-2 d-inline-block text-nowrap"),

                      html.Div([
                        dbc.Input(inputMode='numeric', value="-1.0", className="d-inline-block", style={"width": "4em"}, id="min_corr", debounce=True),
                        html.Span("≤\N{NBSP}correlation\N{NBSP}≤", className="p-2 input-group-text d-inline-block"),
                        dbc.Input(inputMode='numeric', value="1.0", className="d-inline-block", style={"width": "4em"}, id="max_corr", debounce=True),
                      ], className="mb-2 float-right d-inline-block text-nowrap"),

                    ],
                    className="d-flex flex-row justify-content-between flex-wrap"
                  ),
                ]),
                dbc.Row([
                  dbc.Col(
                    [
                      dbc.InputGroup([
                        dbc.InputGroupAddon("Page size", addon_type='prepend'),
                        dbc.Input(inputMode='numeric', value="20", id="page_size", debounce=True),
                      ], style={"width": "11em"}, className="mb-2"),
                    ],
                  ),
                  dbc.Col(
                    dbc.Button("Reset", className="mb-2 float-right", id="reset_corr_settings", color="danger", outline=True,),
                  ),
                ]),
              ], className="p-3")),
              id="corr_table_options_collapse",
              is_open=False,
            ),
            dbc.Row(
              dbc.Col(
                html.Div(
                  dash_table.DataTable(
                    id="corr_table",
                  ),
                  className="pb-3",
                  style={
                    "overflow-x": "scroll",
                  },
                ),
              ),
              className="pt-3",
            ),
          ],
          lg=4,
        ),
      ],
      className="mx-4",
      id='heatmap_container',
      justify='center',
      style=HIDE,
    ),

    html.Div(
      [
        dbc.Row(
          [
            html.H3("Phylogenetic profile plot", id="tree_title"),
          ],
          justify='center',
          id="tree_title_row",
          className='mt-5 mb-0'
        ),
        progress_bar("tree"),
      ],
      id="tree_header",
      style=HIDE,
    ),
    dbc.Row(
      dbc.Col(
        [
          html.Div(
            html.Div([
                html.P("The columns show the orthogroups, with the same name as the query proteins. Rows of the heatmap show the eukaryotic genomes, major taxa on the species tree are labeled with different colors."),
                html.P("To scale the graph use a mouse wheel while holding Alt to scale x axis and/or Ctrl to scale y axis."),
                html.P("Legend:"),
                html.Ul([
                  html.Li([
                    html.Span(className="tree-legend", style={"background-color": "#170a1c"}),
                    html.Span("No findings")
                  ]),
                  html.Li([
                    html.Span(className="tree-legend", style={"background-color": "#666666"}),
                    html.Span("Scheduled to be BLAST'ed")
                  ]),
                  html.Li([
                    html.Span(className="tree-legend", style={"background-color": "#f72585"}),
                    html.Span("Found via BLAST")
                  ]),
                  html.Li([
                    html.Span(className="tree-legend", style={"background-color": "#228cdb"}),
                    html.Span("Found in OrthoDB")
                  ]),
                ]),
              ],
              className="my-2",
              id="tree_help",
              style=HIDE,
            ),
            id="tree-description",
            className="d-none",
          ),
          PhydthreeComponent(
              id="tree_component",
              url=f"/files/{task_id}/tree.xml",
              height=2000,
              taskid_for_links=task_id,
          ),
        ],
        md=10, lg=8,
        className="mx-5 mt-3",
      ),
      justify='center',
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
              dcc.Slider(id="svg_zoom", min=0, max=200, value=100, step=1, updatemode='drag', marks=None),
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

  dbc.Modal(
    [
      dbc.ModalHeader("Cookie consent form"),
      dbc.ModalBody(
        "This website uses cookies to accomplish essential functionality. No user tracking across other websites for advertizing or other purposes is performed."
      ),
      dbc.ModalFooter(
        [
          dbc.Button(
            "Leave",
            id="close-centered",
            color="danger",
            href="https://en.wikipedia.org/wiki/HTTP_cookie",
            external_link=True,
          ),
          dbc.Button(
            "I accept cookies",
            id="accept_cookies_btn",
            color="success",
            external_link=False,
          ),
        ]
      ),
    ],
    id="cookies_consent_modal",
    centered=True,
    is_open=False,
  ),

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
        id='prottree_progress_bar_container',
        className="mx-5 mt-3",
      )
    ),
    dbc.Row(
      dbc.Col(
        PhydthreeComponent(
            id="prottree_tree",
            url=f"/prottree/{prot_id}.xml",
            height=2000,
            leafCount=142,
            show_download_csv=False,
        ),
        className="mx-5 mt-3",
      )
    ),
  ])


def about(app):
    items = [
        html.H3("About", className="mb-3", ),
        html.P([
            html.I("OrthoQuantum"), """ is a web-based tool for visualizing and studying phylogenetic presence/absence patterns of proteins and corresponding orthologous groups."""

        ]),
        html.P("""OrthoQuantum allows the user to submit protein queries, inspect the output in graphic format and download the output in .csv format. The tool visualizes phylogenetic profiles utilizing a set of databases with orthology predictions.  The webserver mainly relies on orthology predictions from the OrthoDB database, which  is leading in coverage of eukaryotic species, with 1,300 species that have a complete or nearly complete genome assembly and 37 million genes/proteins in the most recent update. Clustering of homologous sequences in OrthoDB occurs at the specified taxonomic level."""),
        html.P("""A BLAST search can be performed to complement the orthology data. The user can submit the query in the front page by listing the UniProt identifiers or gene IDs in the input field."""),
        html.P("""This website is free and open to all users and there is no login requirement. Multiple researchers can easily access the tool, which can display data from the set of over 1000 fully sequenced eukaryotic genomes and predicted orthologs at any given time."""),
        html.P("""For brief descriptions, you can hover your mouse on fields to see the tooltip info messages."""),

        sized_img(app.get_asset_url('tutorial/1.png')),

        html.H3("Quick Links to Databases", className="mb-3"),
        html.Ul([
            html.Li(html.A("OrthoDB", href="https://www.orthodb.org")),
            html.Li(html.A("PANTHER", href="http://www.pantherdb.org")),
            html.Li(html.A("NCBI", href="https://www.ncbi.nlm.nih.gov")),
        ]),



        html.H3("Input query details", className="mb-3"),


        html.P("""Available eukaryotic species are divided into taxonomic categories based on “levels of orthology” in OrthoDB: Eukaryota, Metazoa, Viridiplantae, Vertebrata, Aves, Actinopterygii, Fungi, Protista. Users can select sets of target species by using the series of presented drop down menus. For the Eukaryota level there is an option to continue with a compact set of species with a good quality of genome assembly, or with a full set of species that may provide better resolution for conservation patterns ( ‘Eukaryota (compact)’ - 120 species, ‘Eukaryota (all species)’ - 1200 species). Once the source species have been selected, the user can input the sequence IDs in the textbox. Queries can be formulated using synonymous gene/protein names, identifiers, keywords. KEGG Pathway and GO annotations are also available. """),
        sized_img(app.get_asset_url('tutorial/2.png')),

        html.P("""For orthogroups that have missing elements, a search for potential homologs can be conducted against the NCBI non-redundant protein sequence database (nr) using the BlastP algorithm to complement the data from OrthoDB. In this step, users can choose three parameters: E-value threshold, Sequence Identity and Query coverage. Note that OrthoQuantum web-server does not attempt to properly delineate orthologous relationships with BlastP searches, it aims to fill gaps in phylogenetic profiles and demonstrate distribution of homologs of input proteins. """),
        sized_img(app.get_asset_url('tutorial/3.png')),

        html.P("""If a certain entry yields multiple matching orthogroups the user is presented with a table that contains selectable rows with orthogroups. By clicking the 'Submit' button on the bottom of the page, users then proceed to the visualization section. The query can be canceled with ‘Cancel’ button."""),
        sized_img(app.get_asset_url('tutorial/4.png')),

        html.P("""Execute the query by clicking the 'Search' button. The query can be cancelled by clicking ’Cancel’."""),



        html.H3("Results", className="mb-3"),

        html.H5("Orthogroups table"),


        html.P("""A table of information related to each orthogroup is loaded that  links query names with OrthoDB orthogroup identifiers and contains some other useful information about the orthogroups. Genes/proteins that appear in the same group are separated by commas. To see the FASTA-formatted amino acid sequences present in the orthogroup click on the OG label (for example, ‘215502at2759’ for the PIWI proteins orthogroup).  ‘EvolRate’ stands for  ‘Evolutionary rate’ annotation from OrthoDB. It reflects relative sequence conservation among orthologous genes. The numerical data in the columns has filtering capabilities with operators such as >, <, =. """),
        sized_img(app.get_asset_url('tutorial/5.png')),

        html.H5("Correlation matrix", className="mb-3 mt-5"),


        html.P("""The table contains ranked correlations between each pair of proteins with their percentile. The graphic representation of the results is a correlation matrix. The colors on the matrix reflect the values of the Pearson correlation coefficient. On both axes, a color bar is added corresponding to the percentage of homologs present in species: black corresponds to a high percentage and bright red corresponds to a low percentage. """),
        sized_img(app.get_asset_url('tutorial/6.png')),

        html.H5("Phylogenetic Profiles Visualization"),


        html.P("""On the bottom of the page a phylogenetic profile heatmap is constructed. The columns show the orthogroups, with the same name as the query protein name. The order of query sequences is defined by the hierarchical clustering. Rows of the heatmap show the eukaryotic genomes, major taxa on the species tree are labeled with different colors. Mousing over an individual tile in the heatmap reveals the query species, gene names of both the query and orthologous genes.  Clicking on it pins the tooltip and reveals detailed information, including the link to FASTA formatted sequences. """),
        sized_img(app.get_asset_url('tutorial/7.png')),

        html.H5("PantherDB Family/Subfamily Classification Phyloprofile"),


        html.P("""Clicking on the Gene Names generates a phylogenetic profile of subfamilies of homologous proteins in the new browser tab. For example, PIWIL1 gene belongs to PIWI/Aubergine family and has more than 30 related homologous subfamilies. This graph helps to analyze profiles of orthologous groups that contain multiple paralogous genes."""),
        sized_img(app.get_asset_url('tutorial/8.png')),

        html.P("""BlastP hits are visualized on the same phyloprofile plot with OrthoDB orthologs to indicate possible presence of proteins for each orthogroup that has missing elements. BLAST findings are shown in purple, OrthoDB orthology assignments are shown in blue.  We use E-value as the criteria to save the identifiers of best scoring hit. The IDs of findings can be downloaded in .csv format by clicking ‘Download csv’ button in the top right corner of phyloprofile plot.  The heatmap figure can be downloaded as a PNG file by selecting the 'Download Image' button."""),
        sized_img(app.get_asset_url('tutorial/9.png')),

        html.P("""Phyloprofile charts are rendered using SVG model in PhyD3, which is easy to use, but has limited performance. In our tests browsers can typically handle around 1000 orthogroup entries. The user can change the number of displayed proteins to improve performance. In this case, the proteins with the highest absolute values of correlation coefficient will be displayed."""),
        sized_img(app.get_asset_url('tutorial/10.png')),

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
        ], md=10, lg=8),
        justify='center',
    )




print(str(navbar))