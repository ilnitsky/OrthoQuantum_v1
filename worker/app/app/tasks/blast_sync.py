from collections import defaultdict

import pandas as pd
import numpy as np
from scipy.spatial import ConvexHull

from lxml import etree as ET

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
    tree_root = tree.getroot()

    graph = tree_root.find('.//graphs/graph', NS)

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

    return to_blast, name_2_prot, name_to_idx, tree, tree_root

@async_pool.in_thread()
def write_blast_files(req_f, req, taxids_f, taxids):
    req_f.write(req)
    req_f.flush()
    taxids_str = '\n'.join(map(str, taxids))
    taxids_f.write(taxids_str)
    taxids_f.flush()


COLS = {
    'staxid': np.uint32,
    'evalue': np.float64,
    'pident': np.float64,
    'qcovs': np.float64,
}

@async_pool.in_process(max_running=6)
def process_blast_data(res_fn):
    df = pd.read_csv(res_fn, names=list(COLS.keys()), dtype=COLS)
    # replacing 0es with a VERY small value (for log to work)
    df['evalue'].replace(0.0, 1e-100, inplace=True)
    # transforming evalue: log switches it from extremely small numbers (like 10^-100)
    # to reasonable numbers like -100. "-" turns this parameter from "smaller is better"
    # to "larger is better", this way the convex hull point-pruning algorithm works
    df['evalue'] = -np.log10(df['evalue'])

    result = {}

    for taxid, group in df.groupby('staxid', sort=False):
        group: pd.DataFrame
        group = group[group.columns.difference(['staxid'])]
        try:
            if group.shape[0] < 4:
                raise Exception() # ConvexHull would fail, and the dataset already contains just 4 points, don't optimize it
            # Consider only the points that define the convex hull (border) of the parameter space in 3D space
            critical_points = group.iloc[ConvexHull(group.to_numpy()).vertices]
        except Exception:
            critical_points = group
        # filter the poins: exclude points that definetily don't affect the match

        # find indexes of points with max parameter values
        # get points with max parameter values for each parameter (123, 5, 6), (14, 500, 2), etc
        # get minimal values in the set of parameter maximum: (14, 5, 2) for the case above
        # keep all points >= than the parameters found above
        critical_points = critical_points.loc[
            (
                critical_points>=critical_points.loc[
                    critical_points.idxmax()
                ].min()
            ).all(axis=1)
        ]

        result[taxid] = critical_points

    return result

# limited by max blast workers
@async_pool.in_thread()
def write_tree(output_file, tree):
    with open_existing(output_file, 'wb') as f:
        tree.write(f, xml_declaration=True)

