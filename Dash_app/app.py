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

import SPARQLWrapper
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib
import plotly.graph_objects as go

from PIL import Image

from . import user

header = html.H3('Select the name of an Illinois city to see its population!')

output = html.Div(
    id='output',
    children=[],
)


def concat_phylo(im1, im2):
    subprocess.call("./imagemagick.sh")
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
    taxonomy = taxonomy_level.split('-')[0]

    # XXX: injection possible
    with open(f'assets/data/{taxonomy_level}.txt') as organisms_list:
        organisms = organisms_list.readlines()
    # TODO: pre-strip everything in files
    organisms = [x.strip() for x in organisms]

    csv_data = read_csv(user.path() / 'OG.csv', sep=';')
    OG_labels = csv_data['label']
    OG_names = csv_data['Name']

    df = pd.DataFrame(data={"Organisms": organisms}, dtype=object)
    df.set_index('Organisms')
    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

    for i, og_label in enumerate(OG_labels):
        try:
            endpoint.setQuery(f"""prefix : <http://purl.orthodb.org/>
            select
            (count(?gene) as ?count_orthologs)
            ?org_name
            where {{
            ?gene a :Gene.
            ?gene :name ?Gene_name.
            ?gene up:organism/a ?taxon.
            ?taxon up:scientificName ?org_name.
            ?gene :memberOf odbgroup:{og_label}.
            ?gene :memberOf ?og.
            ?og :ogBuiltAt [up:scientificName "{taxonomy}"].
            }}
            GROUP BY ?org_name
            ORDER BY ?org_name
            """)
            endpoint.setReturnFormat(SPARQLWrapper.JSON)

            data = endpoint.query().convert()["results"]["bindings"]
        except Exception:
            data = ()

        # Small trick: preallocating the length of the arrays
        idx = [None] * len(data)
        vals = [None] * len(data)

        for j, res in enumerate(data):
            idx[j] = res["org_name"]["value"]
            vals[j]= res["count_orthologs"]["value"]

        df.merge(pd.Series(vals, index=idx, name=og_label), how='left', on='Organisms')

        # XXX: Debug or output?
        print(100 * i / len(OG_labels))

    # interpret the results:
    df.fillna(0, inplace=True)
    df.to_csv(user.path() / "SPARQLWrapper.csv", index=False)

    df.reset_index(drop=True, inplace=True)

    df['Organisms'] = df['Organisms'].astype("category")
    df['Organisms'].cat.set_categories(organisms, inplace=True)
    df.sort_values(["Organisms"], inplace=True)

    df.columns = ['Organisms', *OG_names]

    df = df[df['Organisms'].isin(organisms)]  #Select Main Species
    df = df.iloc[:, 1:]
    df = df[OG_names]

    for column in df:
        df[column] = df[column].astype(float)

    df.to_csv(user.path() / "Presence-Vectors.csv", index=False)


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

    df = pd.read_csv(user.path() / "SPARQLWrapper.csv")
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

    df4 = read_csv(user.path()/"Presence-Vectors.csv")
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


# def build_graph(city):
#     data = [go.Scatter(x=df.index, y=df[city], marker={'color': 'orange'})]
#     graph = dcc.Graph(figure={'data': data, 'layout': go.Layout(title='{} Population Change'.format(city), yaxis={'title': 'Population'}, hovermode='closest')})
#     return graph
