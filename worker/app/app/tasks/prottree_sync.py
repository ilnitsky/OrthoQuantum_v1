import sqlite3
import pandas as pd
from pathlib import Path

from lxml import etree as ET
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}

from ..async_executor import async_pool

PANTHERDB = "/PANTHERDB/panther.sqlite"
PANTHER_PATH = Path.cwd() / 'panther'


@async_pool.in_process(max_running=1)
def prottree_generator(prot_id:str, prottree_file:str):
    with sqlite3.connect(PANTHERDB) as conn:
        res = conn.execute("""
            SELECT Genome, Gene, Family, Subfamily, Uniprot
            FROM panther
            WHERE PantherID=(
                SELECT PantherID
                FROM panther
                WHERE Gene = ?
            );
        """, (prot_id,))
        data = res.fetchall()
        panther_df = pd.DataFrame(
            data,
            columns=['Genome', 'Gene', 'Family', 'Subfamily', 'Uniprot']
        )

    if panther_df.empty:
        return "No matches found for this protein"
    family = data[0][2].strip("'\" \n\t")

    value_count = panther_df['Subfamily'].value_counts().sort_index(ascending=True)
    value_count = value_count.where(value_count > 8).dropna()
    threshold_families = value_count.index.tolist()

    if len(threshold_families) == 0:
        return "No matches found for this protein"

    panther_df = panther_df.drop_duplicates(subset=['Genome', 'Subfamily'], keep='last').assign(v=1).pivot('Subfamily', 'Genome').fillna(0)
    panther_df = panther_df['v'].T
    panther_df = panther_df[threshold_families]

    tree_taxid = pd.read_csv(PANTHER_PATH / "prottree_id_converter.csv")
    tree_taxid = tree_taxid.merge(panther_df, on='Genome', how='left', copy=False)
    tree_taxid.fillna(0, inplace=True)
    tree_taxid.set_index('TreeID', inplace=True)

    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(str(PANTHER_PATH / "PANTHER.xml"), parser)
    root = tree.getroot()
    # t = root.find("./phylogeny", NS)
    # t.find("./name", NS).text =
    root.find("./phylogeny/description", NS).text = f'Family: "{family}"'

    graphs = ET.SubElement(root, "graphs")
    graph = ET.SubElement(graphs, "graph", type="heatmap")
    ET.SubElement(graph, "name").text = "Presense"
    legend = ET.SubElement(graph, "legend", show="1")

    for col in threshold_families:
        field = ET.SubElement(legend, "field")
        ET.SubElement(field, "name").text = col

    gradient = ET.SubElement(legend, "gradient")
    ET.SubElement(gradient, "name").text = "Custom"
    ET.SubElement(gradient, "classes").text = "2"

    data = ET.SubElement(graph, "data")
    for index, row in tree_taxid.iterrows():
        values = ET.SubElement(data, "values", {"for":str(index)})
        for col in threshold_families:
            ET.SubElement(values, "value").text = f"{row[col] * 100:.0f}"

    with open(prottree_file, 'wb') as f:
        tree.write(f, xml_declaration=True)

    return ""