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