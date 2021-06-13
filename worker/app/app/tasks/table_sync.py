from collections import defaultdict

import SPARQLWrapper
import requests
import pandas as pd
import numpy as np

from ..async_executor import async_pool
from ..utils import open_existing

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
            prot_id,
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
