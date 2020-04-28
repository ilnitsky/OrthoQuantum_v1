
import numpy as np
import pandas as pd
from pandas import DataFrame, read_csv
from astropy.table import Table, Column
from SPARQLWrapper import SPARQLWrapper, JSON
import seaborn as sns
import matplotlib
import matplotlib.pyplot as plt


# wrap the dbpedia SPARQL end-point
endpoint = SPARQLWrapper("http://sparql.orthodb.org/sparql")

# set the query string

# taxonomy_level = "Aves"
# taxonomy_level = "Metazoa"
taxonomy_level = "Eukaryota"
# taxonomy_level = "Vertebrata"


with open(taxonomy_level + ".txt") as organisms_list:
        organisms = organisms_list.readlines()
organisms = [x.strip() for x in organisms]


with open("OG.csv") as OGS:
        OG_list = read_csv('OG.csv', sep=';')['OG']
        OG_names = read_csv('OG.csv', sep=';')['Name']
OG_list = [x.strip() for x in OG_list]



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


# make_view = Table.from_pandas(df_results)
# make_view.show_in_notebook()

# MainSpecies = []
# Prots_to_show = ['MAELSTORM','MLLT1']

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


