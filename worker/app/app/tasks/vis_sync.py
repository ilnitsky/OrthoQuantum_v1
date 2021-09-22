import csv
from logging import exception
import SPARQLWrapper
import pandas as pd
import traceback
from lxml import etree as ET

from ..async_executor import async_pool

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
NS = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "http://www.phyloxml.org"
}

NS_XPATH = {
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "pxml": "http://www.phyloxml.org",
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
        endpoint.setQuery(
            f"""prefix : <http://purl.orthodb.org/>
            select
            ?taxon
            (count(DISTINCT ?Gene_name) as ?count_orthologs)
            (group_concat(DISTINCT ?Gene_name; separator=";") as ?Gene_names)
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


        ortho_counts = {}
        gene_names = {}
        for taxid, orthologs_count, row_gene_names in data:
            taxid = taxid.rsplit('/', maxsplit=1)[-1].strip()
            ortho_counts[taxid] = int(orthologs_count)
            gene_names[taxid] = row_gene_names

        return name, ortho_counts, gene_names
    except Exception:
        try:
            endpoint.setQuery(
                f"""prefix : <http://purl.orthodb.org/>
                select
                ?taxon
                (count(DISTINCT ?Gene_name) as ?count_orthologs)
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

            ortho_counts = {}
            gene_names = {}
            for taxid, orthologs_count in data:
                taxid = taxid.rsplit('/', maxsplit=1)[-1].strip()
                ortho_counts[taxid] = int(orthologs_count)
                gene_names[taxid] = "<sparql error>"

            return name, ortho_counts, gene_names
        except Exception:
            traceback.print_exc()
            return name, None, None


@async_pool.in_process()
def csv_generator(phyloxml_file:str, csv_file:str):
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(phyloxml_file, parser)
    root = tree.getroot()
    heatmap_data = root.find('.//graphs/graph/data', NS)

    orgs_xml = root.xpath("//pxml:id/..", namespaces={'pxml':"http://www.phyloxml.org"})
    # Assuming only children have IDs
    orgs = []
    for org_xml in orgs_xml:
        try:
            orgs.append((int(org_xml.find("id", NS).text), org_xml.find("name", NS).text))
        except Exception:
            # org_id contains letters, this could happen for missing organism
            pass

    with open(csv_file, 'w', newline='') as csvfile:
        spamwriter = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
        row = [""]
        for el in tree.getroot().findall('.//graphs/graph/legend/field/name', NS):
            row.append(el.text)
        spamwriter.writerow(row)
        for tax_id, org_name in orgs:
            row[0] = org_name
            for i, el in enumerate(heatmap_data.xpath(f"(./pxml:values[@for='{tax_id}']/pxml:value)", namespaces=NS_XPATH), 1):
                row[i] = el.attrib.get('label', '-')
            spamwriter.writerow(row)

