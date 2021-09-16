from collections import defaultdict

import pandas as pd
import numpy as np

from lxml import etree as ET
from bs4 import BeautifulSoup

from ..async_executor import async_pool
from ..utils import open_existing


ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}

@async_pool.in_thread(max_running=5)
def load_data(phyloxml_file:str, og_file:str):
    name_2_prot = pd.read_csv(og_file, sep=';', index_col="Name", usecols=["Name", "UniProt_AC"]).to_dict()["UniProt_AC"]

    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(phyloxml_file, parser)
    graph = tree.getroot().find('.//graphs/graph', NS)

    name_to_idx = {
        el.text: idx
        for idx, el in enumerate(graph.iterfind(".//legend/field/name", NS))
    }

    to_blast: defaultdict[str, list[int]] = defaultdict(list)

    for row in graph.iterfind("./data/values", NS):
        try:
            taxid = int(row.attrib['for'])
        except Exception:
            # skip unknown organisms
            continue
        for prot, el in zip(name_to_idx.keys(), row.iterfind("./value", NS)):
            if el.text == "0":
                to_blast[prot].append(taxid)

    return to_blast, name_2_prot, name_to_idx, tree

@async_pool.in_thread()
def write_blast_files(req_f, req, taxids_f, taxids):
    req_f.write(req)
    req_f.flush()
    taxids_str = '\n'.join(map(str, taxids))
    taxids_f.write(taxids_str)
    taxids_f.flush()



COLS = {
    'taxid' : np.uint32,
    'evalue': np.float64,
    'pident': np.float64,
    'qcov'  : np.float64,
}
DF_COLS = tuple(COLS.keys())[1:]
def parse_page(raw_content: bytes):
    soup = BeautifulSoup(raw_content, 'html.parser')

    form = soup.find("form", id="results")
    params = {}
    for inp in form.find_all("input"):
        if 'name' in inp.attrs and 'value' in inp.attrs:
            params[inp['name']] = inp['value']

    columns_to_extract = {
        "Taxid": None,
        "E value": None,
        "Per. Ident": None,
        "Query Cover": None,
    }

    table = soup.find("table", id="dscTable")
    header = table.find("thead").find("tr").find_all("th")
    for idx, col in enumerate(header):
        col_name = col.text.strip()
        if col_name in columns_to_extract:
            columns_to_extract[col_name] = idx

    columns_to_extract = tuple(columns_to_extract.values())

    if None in columns_to_extract:
        raise RuntimeError("Missing columns!")

    data = []
    row = table.find("tbody").find("tr")
    while row:
        tds = row.find_all("td")
        data.append((
            int(tds[columns_to_extract[0]].text.strip("\n ")),
            float(tds[columns_to_extract[1]].text.strip("\n ")),
            float(tds[columns_to_extract[2]].text.strip("\n %")),
            float(tds[columns_to_extract[3]].text.strip("\n %")),
        ))
        row = row.find_next_sibling("tr")
    df = pd.DataFrame(data, columns=COLS.keys())
    return df, params

#in_proces
@async_pool.in_thread(max_running=6)
def extract_table_data(raw_content: bytes) -> tuple[dict[int, pd.DataFrame], dict]:
    """Takes raw page data, returns optimized points for each taxid and params for next request"""

    df, params = parse_page(raw_content)
    del raw_content

    # Removing Evals > 1 (sanity check)
    df.drop(df[df['evalue'] > 1].index, inplace=True)

    # replacing 0es with a VERY small value (for log to work)
    df['evalue'].replace(0.0, 1e-300, inplace=True)

    # transforming evalue: log switches it from extremely small numbers (like 10^-100)
    # to reasonable numbers like -100. "-" turns this parameter from "smaller is better"
    # to "larger is better", this way the point-pruning algorithm works
    # under the assumption "larger is always better" (and all parameters are positive)
    df['evalue'] = -np.log10(df['evalue'])

    result = {}

    for taxid, group in df.groupby('taxid', sort=False):
        group: pd.DataFrame

        points = group[group.columns.difference(['taxid'])].to_numpy()
        # optimizing the number of stored points (since our filters are all >=)
        pts_to_keep = np.empty((0, points.shape[1]))
        points = points[np.argsort(-np.linalg.norm(points, axis=1))]
        while points.size:
            point = points[0,]
            pts_to_keep = np.append(pts_to_keep, [point], axis=0)
            points = points[(points>point).any(axis=1)]

        result[taxid] = pd.DataFrame(pts_to_keep, columns=DF_COLS)

    return result, params

# limited by max blast workers
@async_pool.in_thread()
def write_tree(output_file, tree):
    with open_existing(output_file, 'wb') as f:
        tree.write(f, xml_declaration=True)

