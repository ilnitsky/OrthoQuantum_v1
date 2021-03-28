### Dash
import io
import base64
import os
import subprocess
import time
from past.utils import old_div

import dash_core_components as dcc
import dash_html_components as html

import pandas as pd
from pandas import read_csv

from SPARQLWrapper import SPARQLWrapper, JSON
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib
import plotly.graph_objects as go

from PIL import Image

## Navbar
from navbar import Navbar

nav = Navbar()

endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")

header = html.H3('Select the name of an Illinois city to see its population!')

output = html.Div(
    id='output',
    children=[],
)


def concat_phylo(im1, im2):
    subprocess.call("imagemagick.sh")
    im1 = Image.open(im1)
    im2 = Image.open(im2)
    new_height = 4140
    new_width_im1 = old_div(new_height * im1.width, im1.height)
    new_width_im2 = old_div(new_height * im2.width, im2.height)

    im1 = im1.resize((new_width_im1, new_height), Image.ANTIALIAS)
    im2 = im2.resize((new_width_im2, new_height), Image.ANTIALIAS)

    dst = Image.new('RGB', (im1.width + im2.width, min(im1.height, im2.height)))
    dst.paste(im1, (0, 0))
    dst.paste(im2, (im1.width, (im1.height - im2.height) // 2))
    return dst


def SPARQLWrap(taxonomy_level):

    taxonomy = str(taxonomy_level.split('-')[0])
    with open('assets/data/' + taxonomy_level + ".txt") as organisms_list:
        organisms = organisms_list.readlines()
    organisms = [x.strip() for x in organisms]

    csv_data = read_csv('OG.csv', sep=';')
    OG_list = csv_data['label']
    OG_names = csv_data['Name']
    OG_list = [x.strip() for x in OG_list]

    Prots_to_show = OG_names
    MainSpecies = organisms

    if os.path.isfile('SPARQLWrapper.csv'):
        os.remove("SPARQLWrapper.csv")

    if os.path.isfile('Presence-Vectors.csv'):
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
        """ % (OG, taxonomy)
        endpoint.setQuery(query)
        endpoint.setReturnFormat(JSON)
        results.append(endpoint.query().convert())
        index_of = OG_list.index(i)
        print(100 * index_of / len(OG_list))
        if index_of % 50 == 0:
            time.sleep(1)

    result_table = {"Organisms": organisms}
    df = pd.DataFrame(data=result_table, dtype=object)

    # interpret the results:
    g = 0
    for p in results:

        first_iter_df = pd.DataFrame(columns=["Organisms", OG_list[g]])
        for res in p["results"]["bindings"]:
            second_iter_df = pd.DataFrame([[res["org_name"]["value"], res["count_orthologs"]["value"]]], columns=["Organisms", OG_list[g]])
            first_iter_df = first_iter_df.append(second_iter_df)
        df = pd.merge(df, first_iter_df, on="Organisms", how="left")
        g = g + 1

    df_results = df.fillna(0)
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
    df4 = df4[df4['Organisms'].isin(MainSpecies)]  #Select Main Species
    df4 = df4.iloc[:, 1:]
    df4 = df4[OG_names]
    #SHOW THE PRESENCE VECTORS
    df4 = df4[Prots_to_show]

    for column in df4:
        df4[column] = df4[column].astype(float)

    del taxonomy_level
    del organisms
    del result_table

    df4.to_csv("Presence-Vectors.csv", index=False)


def Correlation_Img(taxonomy_level):
    # taxonomy = str(taxonomy_level.split('-')[0])
    with open('assets/data/' + taxonomy_level + ".txt") as organisms_list:
        organisms = organisms_list.readlines()
    organisms = [x.strip() for x in organisms]
    # print(organisms)

    csv_data = read_csv('OG.csv', sep=';')
    OG_list = csv_data['label']
    OG_names = csv_data['Name']
    OG_list = [x.strip() for x in OG_list]

    df = pd.read_csv("SPARQLWrapper.csv")
    df = df.iloc[:, 1:]
    df.columns = OG_names
    pres_df = df.apply(pd.value_counts).fillna(0)
    pres_df_zero_values = pres_df.iloc[0, :]
    pres_list = [(1 - item / float(len(organisms))) for item in pres_df_zero_values]

    rgbs = [(1 - i, 0, 0) for i in pres_list]
    sns.set(font_scale=1.2)
    df = df.fillna(0).astype(float)
    # df = df.clip(upper=1)
    df = df.loc[:, (df != 0).any(axis=0)]
    dendro = sns.clustermap(
        df.corr(),
        cmap='seismic',
        metric="correlation",
        figsize=(15, 15),
        col_colors=[rgbs],
        row_colors=[rgbs],
    )

    pic_IObytes = io.BytesIO()
    plt.savefig(pic_IObytes, format='png')
    pic_IObytes.seek(0)

    pic_hash = base64.b64encode(pic_IObytes.getvalue()).decode('utf-8')

    # html_text = mpld3.fig_to_html(dendro)

    plt.savefig('assets/images/Correlation.png', dpi=70, bbox_inches="tight")
    return html.Img(src='data:image/png;base64,{}'.format(pic_hash))
    # return html_text


def Presence_Img(taxonomy_level):
    print(taxonomy_level)

    if os.path.isfile('assets/images/Presence.png') == True:
        os.remove('assets/images/Presence.png')

    if os.path.isfile('assets/images/Presence2.png') == True:
        os.remove('assets/images/Presence2.png')

    # taxonomy = str(taxonomy_level.split('-')[0])
    #Create organisms list
    with open('assets/data/' + taxonomy_level + ".txt") as organisms_list:
        organisms = organisms_list.readlines()
    organisms = [x.strip() for x in organisms]
    csv_data = read_csv('OG.csv', sep=';')
    OG_list = csv_data['label']
    OG_names = csv_data['Name']
    OG_list = [x.strip() for x in OG_list]

    Prots_to_show = OG_names
    MainSpecies = organisms

    df4 = read_csv("Presence-Vectors.csv")
    df4 = df4.clip(upper=1)
    # df4 = df4[df4['Organisms'].isin(MainSpecies)]
    levels = [0, 1]
    colors = [
        'yellow',
        'darkgreen',
        # 'darkgreen', 'forestgreen',  'limegreen', 'limegreen', 'lime', 'lime', 'lime', 'lime', 'lime', 'lime'
    ]
    my_cmap, norm = matplotlib.colors.from_levels_and_colors(levels, colors, extend='max')
    sns.set(font_scale=2.2)

    Prots_to_show = Prots_to_show.tolist()

    for idx, item in enumerate(Prots_to_show):
        if '-' in item:
            item = item.split("-")[0]
            Prots_to_show[idx] = item

    phylo = sns.clustermap(
        df4,
        metric="euclidean",
        figsize=(len(Prots_to_show), old_div(len(MainSpecies), 2)),
        # figsize=(len(Prots_to_show)/10, len(MainSpecies)/20),
        linewidth=0.90,
        row_cluster=False,
        #   col_cluster=False,
        cmap=my_cmap,
        norm=norm,
        # yticklabels=MainSpecies,
        xticklabels=Prots_to_show,
        annot=True,
    )

    phylo.cax.set_visible(False)
    phylo.ax_col_dendrogram.set_visible(False)
    # phylo.cax.set_visible(False)
    # ax.tick_params(labeltop=True)

    if os.path.isfile("Presence-Vector.csv"):
        os.remove("Presence-Vector.csv")

    if os.path.isfile('assets/images/concat_phylo.png'):
        os.remove('assets/images/concat_phylo.png')

    plt.savefig('assets/images/Presence.png', dpi=70, bbox_inches="tight")

    png_file = 'assets/images/' + str(taxonomy_level) + '.png'
    concat_phylo(png_file, 'assets/images/Presence.png').save('assets/images/concat_phylo.png')

    phylo2 = sns.clustermap(
        df4,
        metric="euclidean",
        figsize=(len(Prots_to_show), old_div(len(MainSpecies), 2)),
        # figsize=(len(Prots_to_show)/100,len(MainSpecies)/200),
        linewidth=0.90,
        row_cluster=False,
        #   col_cluster=False,
        cmap=my_cmap,
        norm=norm,
        # yticklabels=MainSpecies,
        xticklabels=Prots_to_show,
        annot=True,
    )
    plt.savefig('assets/images/Presence2.png', dpi=70, bbox_inches="tight")
    del taxonomy_level
    del df4

    pic_IObytes = io.BytesIO()
    plt.savefig(pic_IObytes, format='png')
    pic_IObytes.seek(0)
    pic_hash = base64.b64encode(pic_IObytes.getvalue()).decode('utf-8')

    return html.Img(src='data:image/png;base64,{}'.format(pic_hash), style={'height': '612px', 'width': '200px'})


def build_graph(city):
    data = [go.Scatter(x=df.index, y=df[city], marker={'color': 'orange'})]
    graph = dcc.Graph(figure={'data': data, 'layout': go.Layout(title='{} Population Change'.format(city), yaxis={'title': 'Population'}, hovermode='closest')})
    return graph
