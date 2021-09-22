import shutil
import json
from sys import version

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from lxml import etree as ET
import fastcluster
from scipy.cluster import hierarchy

from ..async_executor import async_pool
from ..utils import open_existing

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}

@async_pool.in_process()
def tree(phyloxml_file:str, OG_names: pd.Series, df: pd.DataFrame, organisms: list[str], output_file:str, do_blast:bool, prot_ids):
    df = df[OG_names]

    df.clip(upper=1, inplace=True)
    df.astype(float, copy=False)

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
    ET.SubElement(gradient, "classes").text = "4" if do_blast else "2"

    data = ET.SubElement(graph, "data")
    for index, row in df.iterrows():
        values = ET.SubElement(data, "values", {"for":str(index)})
        for col_idx in reordered_ind:
            el = ET.SubElement(values, "value")
            if row[df.columns[col_idx]]:
                el.text = "100"
                el.attrib["label"] = "OrthoDB: " + prot_ids.get(df.columns[col_idx], {}).get(str(index), "Not Found")
            else:
                el.text = "0"
                if do_blast:
                    el.attrib["label"] = "Not BLASTed"


    with open_existing(output_file, 'wb') as f:
        tree.write(f, xml_declaration=True)

    return df.shape



@async_pool.in_process()
def heatmap(organism_count:int, df: pd.DataFrame, output_file:str, preview_file:str, table_file:str, version:int):
    df.reset_index(drop=True, inplace=True)
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
    tbl_corr = corr.where(np.triu(np.ones(corr.shape), k=1).astype(np.bool)).stack()
    tbl_corr.sort_values(ascending=False, inplace=True)
    tbl_corr = tbl_corr.to_frame("Corr")
    tbl_corr.reset_index(drop=False, inplace=True)
    tbl_corr.columns = ["Prot_A", "Prot_B", "Corr"]

    min_el = tbl_corr["Corr"].iat[0]
    max_el = tbl_corr["Corr"].iat[-1]

    width = max_el - min_el
    if width == 0:
        width = 1
    tbl_corr["Quantile"] = (((min_el-tbl_corr["Corr"]) / width) + 1).round(5)
    tbl_corr["Corr"] = tbl_corr["Corr"].round(5)
    table_data = {
        "version": version,
        "data": {
            "data": tbl_corr.to_dict('records'),
            "columns": [
                {
                    "name": i,
                    "id": i,
                }
                for i in tbl_corr.columns
            ]
        },
    }
    with open_existing(table_file, 'w') as f:
        json.dump(table_data, f, ensure_ascii=False, separators=(',', ':'))

    # 566 - 85/85
    DEFAULT_FIG_SIZE = 10

    if items_count >= 66:
        # generate hi-res version for the click and low-res preview
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
        # hi-res and low-res are the same
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


