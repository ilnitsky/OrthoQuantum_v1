import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Output, Input

import numpy as np
import pandas as pd
from pandas import DataFrame, read_csv
from astropy.table import Table, Column
from SPARQLWrapper import SPARQLWrapper, JSON, POST, POSTDIRECTLY, CSV
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib
import plotly.graph_objects as go
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import dendrogram, linkage, leaves_list
import base64
import os
import json
import subprocess
# import urllib2

endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")
# endpoint.setMethod(POST)
# endpoint.setRequestMethod(POSTDIRECTLY)

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
        print(F)
        i = i + 1

    return handle_list


def new_sparqlwrap():
    # df = pd.read_csv("OG.csv")

    with open('assets/data/Eukaryota-full.txt') as organisms_list:
        organisms = organisms_list.readlines()
    organisms = [x.strip() for x in organisms]

    with open("OG.csv") as OGS:
        OG_list = read_csv('OG.csv', sep=';')['label']
        OG_names = read_csv('OG.csv', sep=';')['Name']
    OG_list = [x.strip() for x in OG_list]

    iOG = [
        '1091011at2759',
        '1471901at2759',
        '349249at2759',
        '1380685at2759',
        '1363547at2759',
        '237430at2759',
        '1622159at2759',
        '1093418at2759',
        '1572458at2759',
        '840669at2759',
    ]

    iOG = OG_list
    print(iOG)
    iOrganisms = ['Trichoplax adhaerens', 'Hydra vulgaris', 'Homo sapiens', 'Gallus gallus', 'Sus scrofa', 'Mus musculus', 'Drosophila melanogaster', 'Loa loa', 'Nicotiana tabacum']

    iOrganisms = organisms

    strng1 = ''
    for i in iOG:
        strng1 = strng1 + 'odbgroup:' + str(i) + ', '
    strng1 = strng1[:-2]

    strng2 = ''
    for i in iOrganisms:
        strng2 = strng2 + '"' + str(i) + '", '
    strng2 = strng2[:-2]

    results = []

    query = """
    prefix : <http://purl.orthodb.org/>
    select (count (?og) as ?ogg)
    ?og
    ?name

    where {
    ?gene a :Gene;  :description ?description; up:organism/a [up:scientificName ?name].
    filter(?name in (%s))
    ?gene :memberOf ?og .
    filter (?og in(
    %s
    ))
    }


    """ % (strng2, strng1)
    # print(query)
    text_file = open("assets/data/sample-query.sparql", "w")
    text_file.write(query)
    text_file.close()

    with open('assets/data/json.txt') as json_dump:
        dictdump = json.loads(json_dump.read())
    # print(type(dictdump))


#     endpoint.setQuery(query)
#     endpoint.setReturnFormat(JSON)
#     results.append(endpoint.query().convert())
# print(results)
    col = ["ogg", "og", "name"]
    results = dictdump

    # og_info = [[]]

    A = []
    B = []
    C = []
    # print(dictdump['results']['bindings'])
    # for p in results:
    for res in dictdump["results"]["bindings"]:
        A.append(res['ogg']['value'])
        B.append(res['og']['value'].split('/')[-1])
        C.append(res['name']['value'])
    data_tuples = list(zip(A, B, C))
    dfs = pd.DataFrame(columns=['counts', 'og', 'organism'], data=data_tuples)
    print(dfs)
    dfs = dfs.sort_values(by=['og'])
    # print(dfs)

    l = []
    data = {}
    for og in iOG:
        dfs_i = dfs[dfs['og'] == og]
        # print(dfs_i['og'].values.tolist())
        mn = dfs_i['og'].values.tolist()[1]
        for i in iOrganisms:
            if i in dfs_i['organism'].values.tolist():
                l.append(1)
            else:
                l.append(0)
        data[mn] = l

        # print(dfs_i['og'])
        # print(l)
        l = []
    new_df = pd.DataFrame.from_dict(data)
    # print(new_df.T.index.tolist())
    Z = linkage(new_df.T)
    # print(leaves_list(Z).tolist())
    old_order_list = new_df.T.index.tolist()
    new_order_list = leaves_list(Z).tolist()
    new_order = [old_order_list[i] for i in new_order_list]
    # print(new_order)
    dendrogram(Z)
    # plt.show()
    # ix = new_df.corr().sort_values
    new_df = new_df[new_order]
    lala = new_df.to_numpy()
    # from sklearn.cluster import AgglomerativeClustering

    # cluster = AgglomerativeClustering(n_clusters=2, affinity='euclidean', linkage='ward')
    # print(cluster.fit_predict(lala))
    # print(pdist(lala, metric='euclidean'))
    fig = go.Figure(data=go.Heatmap(z=new_df.to_numpy(), x=iOG, y=iOrganisms, xgap=2, ygap=2, colorscale='Blues'))

    # def sqdist(vector)
    # return sum(x*x for x in vector)

    # myListOfVectors.sort(key=sqdist)
    fig.show()
    # dfs.groupby(['Animal']).mean()

    # scipy.spatial.distance.pdist


def new_load_og_content():
    i = 1


new_sparqlwrap()
# zip_id_species()
# fasta_from_row()
