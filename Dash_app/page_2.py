import dash
import dash_table 
import dash_core_components as dcc
import dash_html_components as html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash.dependencies import Output, State, Input
import dash_bio as dashbio
import numpy
from bioservices import UniProt
from SPARQLWrapper import SPARQLWrapper, JSON
import pandas as pd
from pandas import DataFrame, read_csv

from app import SPARQLWrap, Correlation_Img, Presence_Img
from homepage import Homepage

import flask
import glob
import os



from navbar import Navbar
nav = Navbar()


image_directory = 'C:/Users/nfsus/OneDrive/best_repository_ever/'
list_of_images = [os.path.basename(x) for x in glob.glob('{}*.png'.format(image_directory))]
print(list_of_images)
static_image_route = '/static/'

body = dbc.Container(
    [
       dbc.Row(
           [
               dbc.Col(
                  [
                     html.H2("Heading"),
                     html.P(
                         """Download presence and study orthology goup presence"""
                           ),
                           dbc.Button("View details", color="secondary"),
                   ],
                  md=4,
               ),
              dbc.Col(
                 [
                    html.Button(id='submit-button2', type='submit', children='Submit')
                        ]
                     ),
                ]
            )
       ],
className="mt-4",
)

og_from_input = html.Div(children=[


    dbc.Row(
        [
        dbc.Col(html.Div("")),

        dbc.Col(html.Div([dcc.Dropdown(
            options=[
                {'label': 'Eukaryota', 'value': 'Eukaryota'},
                {'label': 'Metazoa', 'value': 'Metazoa'},
                {'label': 'Vertebrata', 'value': 'Vertebrata'},
                {'label': 'Tetrapoda', 'value': 'Tetrapoda'},
                {'label': 'Actinopterygii', 'value': 'Actinopterygii'},
                {'label': 'Mammalia', 'value': 'Mammalia'},
                {'label': 'Sauropsida', 'value': 'Sauropsida'},
                {'label': 'Archaea', 'value': 'Archaea'},
                {'label': 'Fungi', 'value': 'Fungi'},
                {'label': 'Lophotrochozoa', 'value': 'Lophotrochozoa'},
                {'label': 'Aves', 'value': 'Aves'},
            ],
            placeholder="Select a taxon (level of orthology)",
            value='Vertebrata',
            id='dropdown'
        ),

          html.Div(id='dd-output-container')
        ]) ),

        dbc.Col(html.Div())

        ]),


    html.Br(),       
    dbc.Row([
        dbc.Col(html.Div()),
        dbc.Col(html.Div([dcc.Textarea(
            id='username',
            placeholder='Enter a value...',
            value='',
            style={'width': '100%'}
            ),
            html.Button(id='submit-button', type='submit', children='Submit'),
          ]  )
        ),    
                       
        dbc.Col(html.Div(
            dcc.Loading(
                    id="loading-2",
                    children=[html.Div([html.Div(id="loading-output-2")])],
                    type="circle",
                )
        )), 
        
        ]),
  
    html.Br(),
    dbc.Row([
        dbc.Col(html.Div()),

        dbc.Col(html.Div(id='output_div')),        
        dbc.Col(html.Div()), 
        
        ]),

])


def Page_2():
    layout = html.Div([
    nav,
    body,
    # submit_button,
    html.Div([
    dcc.Dropdown(
        id='image-dropdown',
        options=[{'label': i, 'value': i} for i in list_of_images],
        value=list_of_images[0]
    ),
    html.Img(id='image')
    ])
   
       ])
    return layout

app = dash.Dash(__name__, external_stylesheets = [dbc.themes.UNITED])
app.config['suppress_callback_exceptions']=True

endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")

app.layout = Page_2()
OG_list = []




# @app.callback(Output('output_div2', 'children'),
#              [Input('submit-button2', 'n_clicks')],
#                           )
# def call(clicks):
#     if clicks is not None:
#         SPARQLWrap()
#         Presence_Img()
#         return html.Img(src='assets/images/Correlation.png')

# @app.callback(Output('dd-output-container', 'children'),
#             [Input('dropdown', 'value')])
# def select_level(value):
#     level = value
#     return 'Selected "{}" orthology level'.format(value)

@app.callback(
    dash.dependencies.Output('image', 'src'),
    [dash.dependencies.Input('image-dropdown', 'value')])
def update_image_src(value):
    return static_image_route + value

# Add a static image route that serves images from desktop
# Be *very* careful here - you don't want to serve arbitrary files
# from your computer or server
@app.server.route('{}<image_path>.png'.format(static_image_route))
def serve_image(image_path):
    image_name = '{}.png'.format(image_path)
    if image_name not in list_of_images:
        raise Exception('"{}" is excluded from the allowed static files'.format(image_path))
    return flask.send_from_directory(image_directory, image_name)




if __name__ == "__main__":
    app.run_server(debug=True)

