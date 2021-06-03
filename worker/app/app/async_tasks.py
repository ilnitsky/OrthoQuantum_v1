from collections import defaultdict
import shutil

import SPARQLWrapper
import requests
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from lxml import etree as ET
import fastcluster
from scipy.cluster import hierarchy

from .async_executor import async_pool
from .utils import open_existing

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}


@async_pool.in_thread(max_running=3)
def orthodb_get(level:str, prot_ids:list) -> defaultdict[str, list]:
    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

    # TODO: think about possible injection here (filter by letters and numbers only?)
    # using INVALID_PROT_IDS to filter all of the nasty possible chars.
    # which are allowed symblos for `level`?
    endpoint.setQuery(f"""
    prefix : <http://purl.orthodb.org/>
    select ?og ?og_description ?gene_name ?xref
    where {{
        ?og a :OrthoGroup;
        :ogBuiltAt [up:scientificName "{level}"];
        :name ?og_description;
        !:memberOf/:xref/:xrefResource ?xref
        filter (?xref in ({', '.join(f'uniprot:{v}' for v in prot_ids)}))
        ?gene a :Gene; :memberOf ?og.
        ?gene :xref [a :Xref; :xrefResource ?xref ].
        ?gene :name ?gene_name.
    }}
    """)
    endpoint.setReturnFormat(SPARQLWrapper.JSON)
    n = endpoint.query().convert()

    # # Tuples of 'label', 'Name', 'PID'
    res = defaultdict(list)

    for result in n["results"]["bindings"]:
        prot_id = result["xref"]["value"].rsplit("/", 1)[-1].strip().upper()
        res[prot_id].append((
            result["og"]["value"].split('/')[-1].strip(),
            result["gene_name"]["value"],
            result["gene_name"]["value"],
        ))

    return res


@async_pool.in_thread(max_running=6)
def uniprot_get(prot_id:str):
    try:
        resp = requests.get(f"http://www.uniprot.org/uniprot/{prot_id}.fasta").text
        fasta_query = "".join(resp.split("\n")[1:])[:100]
        resp = requests.get("https://v101.orthodb.org/blast", params={
            "level": 2,
            "species": 2,
            "seq": fasta_query,
            "skip": 0,
            "limit": 1,
        }).json()
        # Throws exception if not found
        og_handle = resp["data"][0]

        return prot_id, (
            og_handle,
            og_handle,
            prot_id,
        )
    except Exception:
        return prot_id, None

@async_pool.in_thread(max_running=3)
def process_prot_data(data:list[tuple[str, str, str]], output_file:str)-> pd.DataFrame:
    # this uses pandas dataframes, but is not really cpu-bound
    # so we run it in a thread for less overhead and syncronous file io
    uniprot_df = pd.DataFrame(
        columns=['label', 'Name', 'PID'],
        data=data,
    )

    uniprot_df.replace("", np.nan, inplace=True)
    uniprot_df.dropna(axis="index", how="any", inplace=True)
    uniprot_df['is_duplicate'] = uniprot_df.duplicated(subset='label')

    og_list = []
    names = []
    uniprot_ACs = []

    # TODO: DataFrame.groupby would be better, but need an example to test
    for row in uniprot_df[uniprot_df.is_duplicate == False].itertuples():
        dup_row_names = uniprot_df[uniprot_df.label == row.label].Name.unique()
        og_list.append(row.label)
        names.append("-".join(dup_row_names))
        uniprot_ACs.append(row.PID)


    uniprot_df = pd.DataFrame(columns=['label', 'Name', 'UniProt_AC'], data=zip(og_list, names, uniprot_ACs))
    with open_existing(output_file, 'w', newline='') as f:
        uniprot_df.to_csv(f, sep=';', index=False)

    return uniprot_df

@async_pool.in_thread(max_running=50)
def ortho_data_get(requested_ids:list, fields:list) -> dict[str, dict[str, str]]:
    og_string = ', '.join(f'odbgroup:{og}' for og in requested_ids)

    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

    #SPARQL query
    endpoint.setQuery(f"""
    prefix : <http://purl.orthodb.org/>
    select *
    where {{
    ?og a :OrthoGroup;
        rdfs:label ?label;
        :name ?description;
        :ogBuiltAt [up:scientificName ?clade];
        :ogEvolRate ?evolRate;
        :ogPercentSingleCopy ?percentSingleCopy;
        :ogPercentInSpecies ?percentInSpecies;
        :ogTotalGenesCount ?totalGenesCount;
        :ogMultiCopyGenesCount ?multiCopyGenesCount;
        :ogSingleCopyGenesCount ?singleCopyGenesCount;
        :ogInSpeciesCount ?inSpeciesCount;
        :cladeTotalSpeciesCount ?cladeTotalSpeciesCount .
    optional {{ ?og :ogMedianProteinLength ?medianProteinLength}}
    optional {{ ?og :ogStddevProteinLength ?stddevProteinLength}}
    optional {{ ?og :ogMedianExonsCount ?medianExonsCount}}
    optional {{ ?og :ogStddevExonsCount ?stddevExonsCount}}
    filter (?og in ({og_string}))
    }}
    """)
    endpoint.setReturnFormat(SPARQLWrapper.JSON)
    result = endpoint.query().convert()
    og_info = {}

    for og, data in zip(requested_ids, result["results"]["bindings"]):
        try:
            og_info[og] = {
                field: data[field]["value"]
                for field in fields
            }
        except Exception:
            og_info[og] = None

    return og_info


@async_pool.in_thread()
def read_org_info(phyloxml_file:str, og_csv_path:str):
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(phyloxml_file, parser)
    root = tree.getroot()

    orgs_xml = root.xpath("//pxml:id/..", namespaces={'pxml':"http://www.phyloxml.org"})
    # Assuming only children have IDs
    orgs = [
        name
        for _, name in sorted(
            (int(org_xml.find("id", NS).text), org_xml.find("name", NS).text)
            for org_xml in orgs_xml
        )
    ]
    csv_data = pd.read_csv(og_csv_path, sep=';')
    return orgs, csv_data

@async_pool.in_thread(max_pool_share=0.5)
def get_corr_data(label:str, name:str, level:str) -> tuple[str, dict]:
    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

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
        ?gene :memberOf odbgroup:{label}.
        ?gene :memberOf ?og.
        ?og :ogBuiltAt [up:scientificName "{level}"].
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
        vals[j] = int(res["count_orthologs"]["value"])

    return name, {
        res["org_name"]["value"]: int(res["count_orthologs"]["value"])
        for res in data
    }


@async_pool.in_process()
def tree(phyloxml_file:str, OG_names: pd.Series, df: pd.DataFrame, organisms: list[str], output_file:str):
    df['Organisms'] = df['Organisms'].astype("category")
    df['Organisms'].cat.set_categories(organisms, inplace=True)
    df.sort_values(["Organisms"], inplace=True)

    df.columns = ['Organisms', *OG_names]
    df = df[df['Organisms'].isin(organisms)]  #Select Main Species
    df = df.iloc[:, 1:]
    df = df[OG_names]

    df.astype(float, copy=False)
    df.clip(upper=1, inplace=True)

    # Slower, but without fastcluster lib
    # linkage = hierarchy.linkage(data_1, method='average', metric='euclidean')
    link = fastcluster.linkage(df.T.values, method='average', metric='euclidean')
    dendro = hierarchy.dendrogram(link, no_plot=True, color_threshold=-np.inf)

    reordered_ind = dendro['leaves']

    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(phyloxml_file, parser)
    root = tree.getroot()
    graphs = ET.SubElement(root, "graphs")
    graph = ET.SubElement(graphs, "graph", type="heatmap")
    ET.SubElement(graph, "name").text = "Presense"
    legend = ET.SubElement(graph, "legend", show="1")

    for col_idx in reordered_ind:
        field = ET.SubElement(legend, "field")
        ET.SubElement(field, "name").text = df.columns[col_idx]

    gradient = ET.SubElement(legend, "gradient")
    ET.SubElement(gradient, "name").text = "Custom"
    ET.SubElement(gradient, "classes").text = "2"

    data = ET.SubElement(graph, "data")
    for index, row in df.iterrows():
        values = ET.SubElement(data, "values", {"for":str(index)})
        for col_idx in reordered_ind:
            ET.SubElement(values, "value").text = f"{row[df.columns[col_idx]] * 100:.0f}"

    with open_existing(output_file, 'wb') as f:
        tree.write(f, xml_declaration=True)

    return len(organisms)



@async_pool.in_process()
def heatmap(organism_count:int, df: pd.DataFrame, output_file:str, preview_file:str):
    pres_df = df.apply(pd.value_counts).fillna(0)
    pres_df_zero_values = pres_df.iloc[0, :]
    pres_list = [(1 - item / organism_count) for item in pres_df_zero_values]

    rgbs = [(1 - i, 0, 0) for i in pres_list]
    df = df.fillna(0).astype(float)
    df = df.loc[:, (df != 0).any(axis=0)]

    customPalette = sns.color_palette([
        "#f72585","#b5179e","#7209b7","#560bad","#480ca8",
        "#3a0ca3","#3f37c9","#4361ee","#4895ef","#4cc9f0",
    ],as_cmap=True)
    # print(df.describe(), df.shape)
    items_count = df.shape[1]
    corr = df.corr()
    # 566 - 85/85
    DEFAULT_FIG_SIZE = 10

    if items_count >= 66:
        # generate hi-rez version for the click and low-res preview
        size = min(items_count * 0.17, 250) # size when items are readable (+ png size limit)
        sns.clustermap(
            corr,
            cmap=customPalette,
            metric="correlation",
            figsize=(size, size),
            col_colors=[rgbs],
            row_colors=[rgbs],
            yticklabels=True,
            xticklabels=True,
        )
        with open_existing(output_file, 'wb') as f:
            plt.savefig(f, format="png")
        plt.close()

        sns.clustermap(
            corr,
            cmap=customPalette,
            metric="correlation",
            figsize=(DEFAULT_FIG_SIZE, DEFAULT_FIG_SIZE),
            col_colors=[rgbs],
            row_colors=[rgbs],
        )
        with open_existing(preview_file, 'wb') as f:
            plt.savefig(f, format="png")

    else:
        # hi-rez and low-rez are the same
        sns.clustermap(
            corr,
            cmap=customPalette,
            metric="correlation",
            figsize=(DEFAULT_FIG_SIZE, DEFAULT_FIG_SIZE),
            col_colors=[rgbs],
            row_colors=[rgbs],
            yticklabels=True,
            xticklabels=True,
        )
        with open_existing(output_file, 'wb') as f:
            plt.savefig(f, format="png")
        with open_existing(preview_file, 'wb') as fdst, open(output_file, "rb") as fsrc:
            shutil.copyfileobj(fsrc, fdst)


