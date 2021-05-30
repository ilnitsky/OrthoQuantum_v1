from collections import defaultdict
import SPARQLWrapper
import requests

def orthodb_get(level:str, prot_ids:list):
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

def uniprot_get(prot_id:set):
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

        return (
            og_handle,
            og_handle,
            prot_id,
        )
    except Exception:
        return None


def ortho_data_get(requested_ids:list, fields):
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

    og_info = defaultdict(dict)

    for og, data in zip(requested_ids, result["results"]["bindings"]):
        for field in fields:
            og_info[og][field] = data[field]["value"]
    return og_info

