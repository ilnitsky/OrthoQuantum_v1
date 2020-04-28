import numpy as np
import pandas as pd
from pandas import DataFrame, read_csv
from astropy.table import Table, Column
from SPARQLWrapper import SPARQLWrapper, JSON
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt

# taxonomy_level = "Metazoa"
# taxonomy_level = "Eukaryota"
taxonomy_level = "Aves"


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

df4 = read_csv("Presence-Vectors.csv")
df4 = df4.clip_upper(4)
# print(df4)
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
#                         col_cluster=False,
                        cmap=my_cmap, 
                        norm=norm,
                        yticklabels=MainSpecies,
                        xticklabels=Prots_to_show,
                        annot=True,
                       )

# ColorTicks(dendro.ax_heatmap.get_xticklabels())
plt.savefig("Presence.png", dpi = 50, bbox_inches="tight")