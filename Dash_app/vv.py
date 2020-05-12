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
import urllib2




endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")


with open("OG.csv") as OGS:
    OG_list = read_csv('OG.csv', sep=';')['label']
    OG_names = read_csv('OG.csv', sep=';')['Name']
    UniProt_AC = read_csv('OG.csv', sep=';')['UniProt_AC']
OG_list = [x.strip() for x in OG_list]

def load_fasta(id_list):
    handle_list = []
    i = 0
    for id in id_list:
        handle = urllib2.urlopen("http://www.uniprot.org/uniprot/{}.fasta".format(id))
        F = handle.read()
        handle_list.append(str(F))
        print F
        i = i + 1
        
    return handle_list


def fasta_from_row():
    df = pd.read_csv("OG.csv")

    iOG = [
        # '1091011at2759', '1471901at2759',
    '349249at2759',

    ]

    # iOG = OG_list 

    # iOrganisms = ['Camelina sativa', 'Petunia axillaris', 'Solanum tuberosum', 'Sphaeroforma arctica JP610', 'Rhodotorula taiwanensis', 'Capsaspora owczarzaki ATCC 30864']

    # iOrganisms = ['Guillardia theta CCMP2712', 'Ostreococcus lucimarinus CCE9901', 'Solanum tuberosum', 'Sphaeroforma arctica JP610', 'Capsaspora owczarzaki ATCC 30864', 'Homo sapiens']
    # iOrganisms = ['Trichoplax adhaerens', 'Hydra vulgaris', 'Amphimedon queenslandica']

    iOrganisms = ['Gallus gallus']

    strng = ''            
    for i in iOG:
        strng = strng + 'odbgroup:' + str(i) + ', '
    strng = strng[:-2]

    results = []  
    
    query = """    
    prefix : <http://purl.orthodb.org/>
    select
    distinct ?org_name ?xref ?description ?og
    where {
    ?gene a :Gene.
    ?gene :description ?description; :memberOf  ?og.
    filter (?og in (%s))
    ?gene :name ?Gene_name.
    ?gene up:organism/a ?taxon.
    ?taxon up:scientificName ?org_name.
    ?gene :xref [a :Xref; :xrefResource ?xref]. ?xref a :Uniprot.


    }
    GROUP BY ?org_name
    ORDER BY ?og
    """ % (strng)
    
    endpoint.setQuery(query)
    endpoint.setReturnFormat(JSON)
    results.append(endpoint.query().convert())

    col = ["org_name", "xref", "description",  "og"]        

    og_info = [[]]

    for p in results:
        for res in p["results"]["bindings"]:
            og_info_row = []  
            for k in col:
                og_info_row.append(res[k]["value"])        
            og_info.append(og_info_row)
       
    og_info_df = pd.DataFrame(og_info, columns=col)
    og_info_df['og'] = og_info_df['og'].apply(lambda x: str(x).split('/')[-1])
    og_info_df['xref'] = og_info_df['xref'].apply(lambda x: str(x).split('/')[-1])
    

    # print og_info_df
    for b in iOG:
        print '~~~~~~~~~~~~~~~~' + b + '\n' 
        new_df = og_info_df.loc[og_info_df['og'] == b ]
        new_df = new_df[new_df.org_name.isin(iOrganisms)].sort_values(by=['org_name'])
        new_df = new_df.drop_duplicates(subset=['org_name', 'description'], keep='first')
        print new_df
        list_xref = new_df['xref'].tolist()
        print list_xref
        # zz = load_fasta(list_xref)
        
        # print zz    
    # print og_info_df

def zip_id_species():

    with open("try.fasta") as f:
        my_lines = f.readlines()

    
    with open("Book2.csv") as b:
        id = read_csv('Book2.csv', sep=';', error_bad_lines=False)['id']
        taxa = read_csv('Book2.csv', sep=';', error_bad_lines=False)['species']
    zip_id = zip(id,taxa)
    dict_id = dict(zip_id)

    jj = my_lines[0] + my_lines[1]
    # for a, b in dict_id.items():
    #     for line in my_lines:
    #         line = line.replace(a,b)
    jj = ("").join(my_lines)
    for a, b in dict_id.items():
        jj = jj.replace(a,b)
    # print jj
    text_file = open("random.txt", "w")
    text_file.write(jj)


zip_id_species()
# fasta_from_row()