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
import cStringIO
import base64
import os
import os.path


from app import SPARQLWrap, Presence_Img, Correlation_Img



from navbar import Navbar
nav = Navbar()

body = dbc.Container(
    [
       dbc.Row(
           [
               dbc.Col(
                  [
                     html.H2("Heading"),
                     html.P(
                         """Download presence and study orthology group presence
                            Use UniProt Acccesion Codes of your proteins to create a list with corresponding 
                            Orthology groups"""
                           ),
                           dbc.Button("View details", color="secondary"),
                   ],
                  md=4,
               ),
              dbc.Col(
                 [
                     html.H2("Graph"),
                     dcc.Graph(
                         figure={"data": [{"x": [1, 2, 3], "y": [1, 4, 9]}]}
                            ),
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

    html.Br(),
    dbc.Row([
        dbc.Col(html.Div()),

        dbc.Col([
            html.Button(id='submit-button2', type='submit', children='Submit')
        ]),    

        dbc.Col(html.Div()), 
        
        ]),

])


def Homepage():
    layout = html.Div([
    nav,
    body,
    og_from_input,
    html.Div(id='output_div2'),
    # html.Img(src=r'C:\Users\nfsus\OneDrive\best_repository_ever\Dash_app\assets\images\Correlation.png')
   
       ])
    return layout

app = dash.Dash(__name__, external_stylesheets = [dbc.themes.UNITED])
app.config['suppress_callback_exceptions']=True

# df = pd.read_csv("OG_2.csv", sep=";")
endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")
# sparqlwrapper_df = pd.read_csv("SPARQLWrapper.csv", sep=",")

app.layout = Homepage()
OG_list = []


@app.callback(Output('dd-output-container', 'children'),
            [Input('dropdown', 'value')])
def select_level(value):
    level = value
    return 'Selected "{}" orthology level'.format(value)



@app.callback(Output('output_div', 'children'),
             [Input('submit-button', 'n_clicks')],
             [State('username', 'value'), State('dropdown', 'value')],
             )

def update_output(clicks, input_value, dropdown_value):
   
    if clicks is not None:



        if os.path.isfile("SPARQLWrapper.csv") == True:
            os.remove("SPARQLWrapper.csv")


        level = dropdown_value
        input_list = input_value.split()
        u = UniProt()
        Prot_IDs = []
        for Entry in input_list:
            res = u.search('id:' + str(Entry).strip() + ' AND taxonomy:"Mammalia [40674]"',
            frmt='tab', columns='entry name, length, id, genes(PREFERRED)')
            if not res:
                res = 'NotFound'
            else:
                res = res.split('\n')[1].split('\t')[-1]
            Prot_IDs.append(res)
    
    
        uniprot_ac = input_list
        uniprot_name = Prot_IDs
        uniprot_ac = [x.strip() for x in uniprot_ac]
        
        results = []  
        i = 0
        L = []
        M = []
        for i in range(len(uniprot_ac)):
            uniprot_ac_i = uniprot_ac[i]
            uniprot_name_i = uniprot_name[i]
            query = """
            prefix : <http://purl.orthodb.org/>
            select *
            where {
            ?og a :OrthoGroup; 
            :ogBuiltAt [up:scientificName "%s"]; 
            !:memberOf/:xref/:xrefResource uniprot:%s .
            }
            """ % (level, uniprot_ac_i)

            endpoint.setQuery(query)
            endpoint.setReturnFormat(JSON)
            n = endpoint.query().convert()
            
            for Y in n["results"]["bindings"]:

                og_Y_list = []
                og_Y = Y["og"]["value"].split('/')[-1]
                og_Y_list.append(og_Y)
                L.append(uniprot_name_i)
                M.append(og_Y_list[0])

            results.append(endpoint.query().convert())
            results = results
        
        uniprot_df = pd.DataFrame(columns = ['label','Name'])
        data_tuples = list(zip(M,L))
        uniprot_df = pd.DataFrame(columns = ['label','Name'], data = data_tuples)

        uniprot_df['is_duplicate'] = uniprot_df.duplicated(subset='label')
        

        K = []
        J = []
        for row in uniprot_df.itertuples(index=True, name='Pandas'):
            if row.is_duplicate == False:
                rowlist1 = uniprot_df[uniprot_df.label == str(row.label)].Name.tolist()
                
        #remove duplicate names
                rowlist2 =[]
                for i in rowlist1:
                    if i not in rowlist2:
                        rowlist2.append(i)

                K.append("-".join(rowlist2))
                J.append(row.label)

        #SPARQL Look For Presence of OGS in Species        
        OG_list = J
        data_tuples = list(zip(J,K))
        uniprot_df = pd.DataFrame(columns = ['label','Name'], data = data_tuples)
        uniprot_df.to_csv('OG.csv', sep=';', index=False)
        uniprot_json = uniprot_df.to_json()
        uniprot_to_dict = uniprot_df.to_dict()
        
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

        col = ["label","description",  "clade", "evolRate", "totalGenesCount", 
        "multiCopyGenesCount", "singleCopyGenesCount", "inSpeciesCount", "medianExonsCount", "stddevExonsCount", "medianProteinLength",
        "stddevProteinLength",  "og"]        

        og_info = [[]]

        for p in results:
            for res in p["results"]["bindings"]:
                og_info_row = []  
                for k in col:
                    og_info_row.append(res[k]["value"])        
                og_info.append(og_info_row)
        og_info_df = pd.DataFrame(og_info, columns=col)
        og_info_df = pd.merge(og_info_df, uniprot_df, on='label')
        
        cols2 = ["label", "Name", "description",  "clade", "evolRate", "totalGenesCount", 
        "multiCopyGenesCount", "singleCopyGenesCount", "inSpeciesCount", "medianExonsCount", "stddevExonsCount", "medianProteinLength",
        "stddevProteinLength"]   
        og_info_df = og_info_df[cols2]
        


        #prepare datatable update                     
        data = og_info_df.to_dict('rows')
        columns =  [{"name": i, "id": i,} for i in (og_info_df.columns)]
        return dash_table.DataTable(data=data, columns=columns, filter_action="native")



@app.callback(Output('output_div2', 'children'),
             [Input('submit-button2', 'n_clicks')],
                          )
def call(clicks):
    if clicks is not None:
        SPARQLWrap("Vertebrata")
        # corri = Correlation_Img()
        presi = Presence_Img("Vertebrata")

        layout = html.Div([
        # dbc.Row([
        #     dbc.Col(html.Div(corri)),
        # ]),
        
        dbc.Row([
            dbc.Col(html.Div(presi))
        ]),
        
        
        ])
        # if os.path.isfile("OG.csv") == True:
        #     os.remove("OG.csv")
        return layout

if __name__ == "__main__":
    app.run_server()

