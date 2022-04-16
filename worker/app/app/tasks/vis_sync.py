import csv
from logging import exception
import SPARQLWrapper
import pandas as pd
import sqlite3
from ..db import ORTHODB
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

# Extracted from odb10v1_species.tab:
# some use
_ID_TRANSLATION_TBL = {
    441894: 8801,
    381198: 8845,
    216574: 8962,
    74533: 9694,
    62698: 9708,
    310752: 9767,
    127582: 9778,
    73337: 9807,
    1230840: 9818,
    43346: 9901,
    299123: 40157,
    556262: 100884,
    319938: 288004,
    1841481: 302047,
    1505932: 408180,
    595593: 656366,
    667632: 863227,
    1336249: 1367849,
    1220582: 1368415,
    1834200: 1796646,
    1166016: 1905730,
}

@async_pool.in_process(max_pool_share=0.5)
def get_corr_data(csv_data) -> tuple[str, dict]:
    corr_info = {}
    prot_ids = {}

    with sqlite3.connect(ORTHODB) as conn:
        for _, data in csv_data.iterrows():
            name = data['Name']
            label = data['label']

            cluster_id, clade = map(int, label.split('at', maxsplit=1))
            ortho_counts = {}
            gene_names = {}

            cur = conn.execute("""
                    SELECT orthodb_id>>32 AS taxid, count(distinct orthodb_id), GROUP_CONCAT(distinct gene_name)
                    FROM orthodb_to_og
                    LEFT JOIN genes USING (orthodb_id)
                    WHERE
                        clade=? AND cluster_id=?
                    GROUP BY taxid
                """, (clade, cluster_id))
            req_res = cur.fetchall()
            for taxid, orthologs_count, row_gene_names in req_res:
                taxid = _ID_TRANSLATION_TBL.get(taxid, taxid)
                ortho_counts[taxid] = orthologs_count
                gene_names[taxid] = row_gene_names.replace(",", ", ") if row_gene_names is not None else "None"

            corr_info[name] = ortho_counts
            prot_ids[name] = gene_names

    return corr_info, prot_ids

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

