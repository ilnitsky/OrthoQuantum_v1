#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fileencoding=utf-8

import numpy as np
import pandas as pd
from pandas import DataFrame, read_csv
from astropy.table import Table, Column
from SPARQLWrapper import SPARQLWrapper, JSON
import seaborn as sns
import matplotlib.pyplot as plt


# taxonomy_level = "Metazoa"
# taxonomy_level = "Aves"
taxonomy_level = "Eukaryota"


#Create organisms list
with open(taxonomy_level + ".txt") as organisms_list:
        organisms = organisms_list.readlines()
organisms = [x.strip() for x in organisms]

#Create orthology group list
with open("OG.csv") as OGS:
        OG_list = read_csv('OG.csv', sep=';')['OG']
        OG_names = read_csv('OG.csv', sep=';')['Name']
OG_list = [x.strip() for x in OG_list]

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

# # ColorTicks(dendro.ax_heatmap.get_yticklabels())
# # ColorTicks(dendro.ax_heatmap.get_xticklabels())

# plt.show()
plt.savefig("Correlation.png")
