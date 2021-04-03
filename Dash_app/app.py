### Dash
import subprocess

import pandas as pd
from pandas import read_csv

import SPARQLWrapper
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib

from PIL import Image

from . import user

def concat_phylo(taxonomy_path, presence_path):
    subprocess.call([
        "convert",
        presence_path,
        "-trim",
        presence_path,
    ])

    im1 = Image.open(taxonomy_path)
    im2 = Image.open(presence_path)
    new_height = 4140
    new_width_im1 = new_height * im1.width // im1.height
    new_width_im2 = new_height * im2.width // im2.height

    im1 = im1.resize((new_width_im1, new_height), Image.ANTIALIAS)
    im2 = im2.resize((new_width_im2, new_height), Image.ANTIALIAS)

    dst = Image.new('RGB', (im1.width + im2.width, min(im1.height, im2.height)))
    dst.paste(im1, (0, 0))
    dst.paste(im2, (im1.width, (im1.height - im2.height) // 2))
    return dst


def SPARQL_wrap(taxonomy_level):
    taxonomy = taxonomy_level.split('-')[0]

    # TODO: injection possible
    with open(f'assets/data/{taxonomy_level}.txt') as organisms_list:
        organisms = organisms_list.readlines()

    # TODO: pre-strip everything in files to remove this
    # and similar lines in the codebase
    organisms = [x.strip() for x in organisms]

    csv_data = read_csv(user.path() / 'OG.csv', sep=';')
    OG_labels = csv_data['label']
    OG_names = csv_data['Name']

    df = pd.DataFrame(data={"Organisms": organisms}, dtype=object)
    df.set_index('Organisms', inplace=True)
    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

    for i, (og_label, og_name) in enumerate(zip(OG_labels, OG_names)):
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
            vals[j]= int(res["count_orthologs"]["value"])

        df[og_name] = pd.Series(vals, index=idx, name=og_name, dtype=int)

        # TODO: Debug or output?
        print(100 * i / len(OG_labels))

    # interpret the results:
    df.fillna(0, inplace=True)

    df.reset_index(drop=False, inplace=True)
    df.to_csv(user.path() / "SPARQLWrapper.csv", index=False)

    # TODO: What's the purpose of this code?

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


def correlation_img(taxonomy_level):
    # taxonomy = str(taxonomy_level.split('-')[0])
    with open(f'assets/data/{taxonomy_level}.txt') as organisms_list:
        organisms = organisms_list.readlines()
    organisms = [x.strip() for x in organisms]

    csv_data = read_csv(user.path() / 'OG.csv', sep=';')
    OG_names = csv_data['Name']

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

    sns.clustermap(
        df.corr(),
        cmap='seismic',
        metric="correlation",
        figsize=(15, 15),
        col_colors=[rgbs],
        row_colors=[rgbs],
    )
    # TODO: replace static filenames to dynamic (perhaps based on hash of request)
    file_name = "Correlation.png"

    # TODO: what to serve? do we need  dpi=70, bbox_inches="tight" ?
    plt.savefig(user.path()/file_name)
    return user.url_for(file_name)
    # return html_text

def presence_img(taxonomy_level):
    print(taxonomy_level)

    #Create organisms list
    with open(f'assets/data/{taxonomy_level}.txt') as organisms_list:
        organisms = organisms_list.readlines()
    organisms = [x.strip() for x in organisms]
    csv_data = read_csv(user.path() / 'OG.csv', sep=';')
    og_names = csv_data['Name']
    main_species = organisms

    df4 = read_csv(user.path()/"Presence-Vectors.csv")
    df4 = df4.clip(upper=1)

    levels = [0, 1]
    colors = [
        'yellow',
        'darkgreen',
        # 'darkgreen', 'forestgreen',  'limegreen', 'limegreen', 'lime', 'lime', 'lime', 'lime', 'lime', 'lime'
    ]
    my_cmap, norm = matplotlib.colors.from_levels_and_colors(levels, colors, extend='max')
    sns.set(font_scale=2.2)

    prots_to_show = [x.split("-", maxsplit=1)[0] for x in og_names]

    phylo = sns.clustermap(
        df4,
        metric="euclidean",
        figsize=(len(prots_to_show), len(main_species) // 2),
        # figsize=(len(Prots_to_show)/10, len(MainSpecies)/20),
        linewidth=0.90,
        row_cluster=False,
        #   col_cluster=False,
        cmap=my_cmap,
        norm=norm,
        # yticklabels=MainSpecies,
        xticklabels=prots_to_show,
        annot=True,
    )

    phylo.cax.set_visible(False)
    phylo.ax_col_dendrogram.set_visible(False)

    plt.savefig(user.path() / 'Presence.png', dpi=70, bbox_inches="tight")

    concat_img = concat_phylo(
        f'assets/images/{taxonomy_level}.png',
        str(user.path() / 'Presence.png')
    )
    concat_phylo_filename = 'concat_phylo.png'
    concat_img.save(user.path() / concat_phylo_filename)

    sns.clustermap(
        df4,
        metric="euclidean",
        figsize=(len(prots_to_show), len(main_species) // 2),
        # figsize=(len(Prots_to_show)/100,len(MainSpecies)/200),
        linewidth=0.90,
        row_cluster=False,
        #   col_cluster=False,
        cmap=my_cmap,
        norm=norm,
        # yticklabels=MainSpecies,
        xticklabels=prots_to_show,
        annot=True,
    )

    presence_name = 'Presence2.png'
    # TODO: what to serve? do we need  dpi=70, bbox_inches="tight" ?
    plt.savefig(user.path() / presence_name)
    return user.url_for(concat_phylo_filename), user.url_for(presence_name)
