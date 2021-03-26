import numpy as np
import pandas as pd
from pandas import DataFrame, read_csv
from astropy.table import Table, Column
from SPARQLWrapper import SPARQLWrapper, JSON
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt

# taxonomy_level = "Metazoa"
taxonomy_level = "Eukaryota-full"
# taxonomy_level = "Aves"


with open('/home/ken/best_repository_ever/Dash_app/assets/data/' + taxonomy_level + ".txt") as organisms_list:
        organisms = organisms_list.readlines()
organisms = [x.strip() for x in organisms]
with open("OG.csv") as OGS:
    OG_list = read_csv('OG.csv', sep=';')['label']
    OG_names = read_csv('OG.csv', sep=';')['Name']
OG_list = [x.strip() for x in OG_list]


Prots_to_show = OG_names
MainSpecies = organisms

df4 = read_csv("Presence-Vectors.csv")
df4 = df4.clip(upper=1)
# print(df4)
# df4 = df4[df4['Organisms'].isin(MainSpecies)]

levels = [0,1]
colors = ['yellow', 'darkgreen']
my_cmap, norm = matplotlib.colors.from_levels_and_colors(levels, colors, extend='max')
print(df4.iloc[:10])
# df4 = df4.iloc[:10]
# sns.set(font_scale=2.2)
# dendro = sns.clustermap(df4, metric="euclidean", 
                        # figsize=(len(Prots_to_show)/10,len(MainSpecies)/20), 
                        # linewidth=0.90,
                        # row_cluster=False,
                        # col_cluster=False,
                        # cmap=my_cmap, 
                        # norm=norm,
                        # yticklabels=MainSpecies,
                        # xticklabels=Prots_to_show,
                        # annot=True,
                    #    )
# plt.tight_layout()
fig, ax = plt.subplots(figsize=(240, 380))
# hm = sns.heatmap(df4)

hm = sns.clustermap(df4, figsize=(len(Prots_to_show)/5, len(MainSpecies)/20),  row_cluster=False, annot=True, linewidth=0.20, cmap=my_cmap, norm=norm)
# ColorTicks(dendro.ax_heatmap.get_xticklabels())
plt.savefig("Presence11111111.eps", dpi = 50, bbox_inches="tight", format='eps')
# plt.show()