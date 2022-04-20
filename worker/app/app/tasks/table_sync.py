from collections import defaultdict
import re

import SPARQLWrapper
import requests
import pandas as pd
import numpy as np

import sqlite3

from ..async_executor import async_pool
from ..utils import open_existing, decode_int
from ..db import ORTHODB

@async_pool.in_thread(max_running=3)
def orthodb_get(level_id:int, prot_ids:list[str]) -> defaultdict[str, list]:
    # from requested ids here we get:
    # https://v101.orthodb.org/fasta?query=Q92484&level=7742&species=7742&universal=&singlecopy=
    # SMPDL3A - pub_gene_id
    # 164772at7742 - pub_og_id

    # Clade=level=dropdown value
    #                  'label',       'Name',    'PID'
    # {
    #     "A6NK59": [("125442at7742", "ASB14", "A6NK59")],
    #     "P05026": [("276599at7742", "ATP1B1", "P05026")],
    #     "P39687": [("413605at7742", "ANP32A", "P39687")],
    #     "P51451": [("177888at7742", "BLK", "P51451")],
    #     "Q5T1B0": [("91060at7742", "AXDND1", "Q5T1B0")],
    #     "Q92484": [("164772at7742", "SMPDL3A", "Q92484")]
    # }


    res = defaultdict(lambda: defaultdict(list))
    with sqlite3.connect(ORTHODB) as conn:
        cur = conn.execute(f"""
            SELECT
            printf("%dat%d", cluster_id, clade), gene_name, uniprot_id
            FROM genes
            LEFT JOIN orthodb_to_og USING (orthodb_id)
            WHERE
                clade=?
                AND
                genes.uniprot_id IN ({('?,'*len(prot_ids))[:-1]})
            ;
        """, (level_id, *prot_ids))
        for label, name, prot_id in cur:
            res[prot_id][label].append(name)
        for prot_id in res:
            for label in res[prot_id]:
                res[prot_id][label] = ', '.join(res[prot_id][label])
    return res

SPLITTER = re.compile(r"[_:]")
def str_to_orthodb_id(s:str)->int:
    res = SPLITTER.split(s, maxsplit=2)
    assert len(res) == 3, s
    return int(res[0], 10)<<32 | int(res[1], 10) << 24 | int(res[2], 16)

@async_pool.in_process(max_running=5)
def orthodb_get_gene_name(ortho_id:str, species:str) -> list[tuple[str, str]]:
    cluster_id, clade = decode_int(*ortho_id.split('at', maxsplit=1))
    species = int(species)
    # 9103_0:004161
    # (a << (32)) | (b << 24) | c, nil
    with sqlite3.connect(ORTHODB) as conn:
        cur = conn.execute(f"""
        SELECT genes.gene_name, genes.uniprot_id
        FROM genes
        LEFT JOIN orthodb_to_og USING (orthodb_id)
        WHERE
            orthodb_to_og.cluster_id=? AND
            orthodb_to_og.clade=? AND
            orthodb_to_og.orthodb_id>>32=?
        ;
        """, [cluster_id, clade, species])
        res = cur.fetchall()
    return tuple(zip(*res))


@async_pool.in_process(max_running=5)
def orthodb_get_uniprot(orthodb_ids:list[set[str]]) -> defaultdict[str, list]:
    # 9103_0:004161
    # (a << (32)) | (b << 24) | c, nil
    req = [str_to_orthodb_id(s) for s in set.union(*orthodb_ids)]
    with sqlite3.connect(ORTHODB) as conn:
        cur = conn.execute(f"""
            SELECT
            orthodb_id, uniprot_id
            FROM genes
            WHERE
                orthodb_id IN ({('?,'*len(req))[:-1]})
            ;
        """, req)
        res = cur.fetchall()
    res = dict(res)
    result = []
    for s in orthodb_ids:
        for id in s:
            r = res.get(str_to_orthodb_id(id))
            if r:
                result.append(r)
                break
        else:
            result.append(None)
    return result

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

@async_pool.in_thread(max_running=3)
def process_prot_data(data:list[tuple[str, str, str]], output_file:str)-> pd.DataFrame:
    # this uses pandas dataframes, but is not really cpu-bound
    # so we run it in a thread for less overhead and syncronous file io
    uniprot_df = pd.DataFrame(
        columns=['req', 'label', 'Name', 'PID'],
        data=data,
    )

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

@async_pool.in_thread()
def pickle_df(file, og_info_df:pd.DataFrame):
    og_info_df.to_pickle(file)
    # with open(file, "w") as f:
    #     json.dump(table_data, f, ensure_ascii=False, separators=(',', ':'))