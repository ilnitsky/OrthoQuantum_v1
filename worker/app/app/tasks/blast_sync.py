from collections import defaultdict
import subprocess
import tempfile

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

# limited by blast task count
@async_pool.in_process(max_running=2)
def blast(prot_fasta:str, tax_ids:list[str]):
    with (tempfile.NamedTemporaryFile("w", suffix=".req_file.fa") as req_f,
        tempfile.NamedTemporaryFile("w", suffix=".taxids") as taxids_f,
        tempfile.NamedTemporaryFile("r", suffix=".blast_result.csv") as res_f):
        req_f.write(prot_fasta)
        req_f.flush()
        taxids_str = '\n'.join(map(str, tax_ids))
        taxids_f.write(taxids_str)
        taxids_f.flush()

        cols = {
            'staxid': np.uint32,
            'evalue': np.float64,
            'pident': np.float64,
            'qcovs': np.float64,
        }

        exit_code = subprocess.call([
            "blastp",
            "-query", req_f.name,
            "-taxidlist", taxids_f.name,
            "-out", res_f.name,
            "-db", "/blast/blastdb/nr.00",
            "-evalue", "1e-3", # the system relies on E < 1 (because we're using log).
            "-max_target_seqs", "2000",
            "-outfmt", f"10 {' '.join(cols.keys())}",
            "-num_threads", "4",
        ])

        df = pd.read_csv(res_f, names=list(cols.keys()), dtype=cols)
        df['evalue'].replace(0.0, 1e-100, inplace=True)
        df['evalue'] = -np.log10(df['evalue'])

        result = {}

        for taxid, group in df.groupby('staxid', sort=False): # for loop
            group: pd.DataFrame
            group = group[group.columns.difference(['staxid'])]
            try:
                if group.shape[0] < 4:
                    raise Exception() # ConvexHull would fail
                critical_points = group.iloc[ConvexHull(group.to_numpy()).vertices]
            except Exception:
                critical_points = group
            critical_points = critical_points.loc[(critical_points>=critical_points.loc[critical_points.idxmax()].min()).all(axis=1)]

            result[taxid] = critical_points

        return result

# limited by max blast workers
@async_pool.in_thread()
def write_tree(output_file, tree):
    with open_existing(output_file, 'wb') as f:
        tree.write(f, xml_declaration=True)

