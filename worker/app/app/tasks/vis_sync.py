import csv
import SPARQLWrapper
import pandas as pd
from lxml import etree as ET

from ..async_executor import async_pool

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}

@async_pool.in_thread()
def read_org_info(phyloxml_file:str, og_csv_path:str):
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(phyloxml_file, parser)
    root = tree.getroot()

    orgs_xml = root.xpath("//pxml:id/..", namespaces={'pxml':"http://www.phyloxml.org"})
    # Assuming only children have IDs
    orgs = []
    for org_xml in orgs_xml:
        try:
            org_id = org_xml.find("id", NS).text
            orgs.append(int(org_id))
        except Exception:
            # org_id contains letters, this could happen for missing organ
            pass

    csv_data = pd.read_csv(og_csv_path, sep=';')
    return orgs, csv_data

@async_pool.in_thread(max_pool_share=0.5)
def get_corr_data(label:str, name:str, level:str) -> tuple[str, dict]:
    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

    try:
        endpoint.setQuery(f"""prefix : <http://purl.orthodb.org/>
            select
            ?taxon
            (count(?gene) as ?count_orthologs)
            where {{
            ?gene a :Gene.
            ?gene :name ?Gene_name.
            ?gene up:organism/a ?taxon.
            ?gene :memberOf odbgroup:{label}.
            ?gene :memberOf ?og.
            ?taxon up:scientificName ?org_name.
            ?og :ogBuiltAt [up:scientificName "{level}"].
            }}
            GROUP BY ?taxon
            ORDER BY ?taxon
        """)
        endpoint.setReturnFormat(SPARQLWrapper.CSV)

        data = csv.reader(endpoint.query().convert().decode().strip().split("\n")[1:])
    except Exception:
        data = ()

    return name, {
        int(taxid.rsplit('/', maxsplit=1)[-1].strip()): int(orthologs_count)
        for taxid, orthologs_count in data
    }
