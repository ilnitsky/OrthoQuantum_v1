### Dash
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Output, Input

import numpy as np
import pandas as pd
from pandas import DataFrame, read_csv
from astropy.table import Table, Column
from SPARQLWrapper import SPARQLWrapper, JSON
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib
import plotly.graph_objects as go
import cStringIO
import base64
import os

## Navbar
from navbar import Navbar

nav = Navbar()

endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")

taxonomy_level = "Vertebrata"

    #Create organisms list
with open(taxonomy_level + ".txt") as organisms_list:
    organisms = organisms_list.readlines()
organisms = [x.strip() for x in organisms]

#Create orthology group list
with open("OG.csv") as OGS:
    OG_list = read_csv('OG.csv', sep=';')['label']
    OG_names = read_csv('OG.csv', sep=';')['Name']
OG_list = [x.strip() for x in OG_list]

Prots_to_show = OG_names
MainSpecies = organisms


header = html.H3(
    'Select the name of an Illinois city to see its population!'
)


output = html.Div(id = 'output',
                children = [],
                )

def App():
    layout = html.Div([
        nav,
        header,
        html.Img(src='assets/images/Correlation.png')
        
    ])
    return layout




def SPARQLWrap():
    os.remove("SPARQLWrapper.csv")
    os.remove("Presence-Vectors.csv")
    results = []  
    for i in OG_list:
        OG = i + "."
        query = """prefix : <http://purl.orthodb.org/>
        select 
        (count(?gene) as ?count_orthologs)
        ?org_name
        where {
        ?gene a :Gene.
        ?gene :name ?Gene_name.
        ?gene up:organism/a ?taxon.
        ?taxon up:scientificName ?org_name.
        ?gene :memberOf odbgroup:%s
        ?gene :memberOf ?og.
        ?og :ogBuiltAt [up:scientificName "%s"].
        }
        GROUP BY ?org_name
        ORDER BY ?org_name
        """ % (OG, taxonomy_level)
        endpoint.setQuery(query)
        endpoint.setReturnFormat(JSON)
        results.append(endpoint.query().convert())

      
    result_table = {"Organisms":organisms}
    df = pd.DataFrame(data=result_table,dtype=object)

    # interpret the results:
    g = 0
    for p in results:
    
        first_iter_df = pd.DataFrame(columns=["Organisms", OG_list[g]])
        for res in p["results"]["bindings"]:
            second_iter_df = pd.DataFrame([[ res["org_name"]["value"],
                                        res["count_orthologs"]["value"] ]], 
                                        columns=["Organisms", OG_list[g]])
            first_iter_df = first_iter_df.append(second_iter_df)
        df = pd.merge(df, first_iter_df, on="Organisms", how="left")
        g = g + 1

    df_results=df.fillna(0)
    df_results.columns = pd.concat([pd.Series(['Organisms']), OG_names])
    df_results.to_csv("SPARQLWrapper.csv", index=False)

    Prots_to_show = OG_names
    MainSpecies = organisms

    df4 = df_results.reset_index(drop=True)
    df4['Organisms'] = df4['Organisms'].astype("category")
    df4['Organisms'].cat.set_categories(MainSpecies, inplace=True)
    df4 = df4.sort_values(["Organisms"])
    OG_names_1 = ['Organisms']
    OG_names_1.extend(OG_names)
    df4.columns = OG_names_1
    df4 = df4[df4['Organisms'].isin(MainSpecies)] #Select Main Species
    df4 = df4.iloc[:, 1:]
    df4 = df4[OG_names]
    #SHOW THE PRESENCE VECTORS
    df4 = df4[Prots_to_show]

    for column in df4:    
        df4[column] = df4[column].astype(float)

    df4.to_csv("Presence-Vectors.csv", index=False)


def Correlation_Img():

    # OG_list = [x.strip() for x in OG_list]
    df = pd.read_csv("SPARQLWrapper.csv")
    df = df.iloc[:, 1:]
    df.columns = OG_names
    pres_df = df.apply(pd.value_counts).fillna(0)
    pres_df_zero_values = pres_df.iloc[0, :]
    pres_list = [(1 - item/float(len(organisms))) for item in pres_df_zero_values]

    rgbs = [(1-i,0,0) for i in pres_list]

    df = df.fillna(0).astype(float)
    dendro = sns.clustermap(df.corr(), 
                        cmap='seismic',
                        metric="correlation",
                        figsize=(15,15), 
                        col_colors=[rgbs],
                        row_colors=[rgbs],
    )
    my_stringIObytes = cStringIO.StringIO()
    plt.savefig(my_stringIObytes, format='png')
    my_stringIObytes.seek(0)
    my_base64_pngData = base64.b64encode(my_stringIObytes.read())

    return html.Img(src='data:image/png;base64,{}'.format(my_base64_pngData))




def Presence_Img():

    df4 = read_csv("Presence-Vectors.csv")
    df4 = df4.clip(upper=4)
    # df4 = df4[df4['Organisms'].isin(MainSpecies)]
    levels = [0, 1, 2, 3, 4]
    colors = ['yellow', 'darkgreen', 'darkgreen', 'darkgreen', 'darkgreen'
    # 'darkgreen', 'forestgreen',  'limegreen', 'limegreen', 'lime', 'lime', 'lime', 'lime', 'lime', 'lime'
    ]
    my_cmap, norm = matplotlib.colors.from_levels_and_colors(levels, colors, extend='max')
    sns.set(font_scale=2.2)
    dendro = sns.clustermap(df4, metric="euclidean", 
                        figsize=(len(Prots_to_show),len(MainSpecies)/2), 
                        linewidth=0.90,
                        row_cluster=False,
    #                   col_cluster=False,
                        cmap=my_cmap, 
                        norm=norm,
                        yticklabels=MainSpecies,
                        xticklabels=Prots_to_show,
                        annot=True,
                       )

    # ColorTicks(dendro.ax_heatmap.get_xticklabels())
    # plt.savefig('C:/Users/nfsus/OneDrive/best_repository_ever/Dash_app/assets/Presence.png', dpi = 70, bbox_inches="tight")
    
    # plt.savefig(r'C:\Users\nfsus\OneDrive\best_repository_ever\Dash_app\assets\images\Presence.png', dpi = 70, bbox_inches="tight")
    my_stringIObytes = cStringIO.StringIO()
    plt.savefig(my_stringIObytes, format='png')
    my_stringIObytes.seek(0)
    my_base64_pngData = base64.b64encode(my_stringIObytes.read())

    return html.Img(src='data:image/png;base64,{}'.format(my_base64_pngData))



    # layout = html.Div([
    #     nav,
    #     html.Img(src='assets/images/Presence.png')
    # ])
    # return layout 


def build_graph(city):
    data = [go.Scatter(x = df.index,
                        y = df[city],
                        marker = {'color': 'orange'})]
    graph = dcc.Graph(
           figure = {
               'data': data,
               'layout': go.Layout(
                    title = '{} Population Change'.format(city),
                    yaxis = {'title': 'Population'},
                    hovermode = 'closest'
                                  )
                       }
             )
    return graph

