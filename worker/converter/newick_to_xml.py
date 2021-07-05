import csv
import re
from pathlib import Path
from lxml import etree as ET
from lxml.builder import ElementMaker
import SPARQLWrapper

tokens = re.compile(r"[^(),;]+|\(|\)|,|;")

def convert(newick_file, phyloxml_file, level, taxa_colors={}):
    endpoint = SPARQLWrapper.SPARQLWrapper("http://sparql.orthodb.org/sparql")

    endpoint.setQuery(f"""
    prefix : <http://purl.orthodb.org/>
    select ?tax_id, ?tx_name
    where {{
        ?clade a :Clade; up:scientificName "{level}".
        ?tax_id a :Species; up:scientificName ?tx_name; rdfs:subClassOf+ ?clade.
        ?org a :Organism,?tax_id; up:scientificName ?org_name.
    }}
    """)
    endpoint.setReturnFormat(SPARQLWrapper.CSV)
    n = endpoint.query().convert().decode().strip().split('\n')[1:]
    taxids = {
        name: taxid.rsplit("/", maxsplit=1)[-1]
        for taxid, name in csv.reader(n)
    }
    taxid_name_conv = {
        name.strip().lower(): name
        for name in taxids
    }

    with open(newick_file) as f:
        newick = f.read().strip()

    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    NS = {
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        None: "http://www.phyloxml.org"
    }
    E = ElementMaker(
        namespace="http://www.phyloxml.org",
        nsmap={
            None: "http://www.phyloxml.org",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        }
    )
    my_doc = E.phyloxml(
        {"{http://www.w3.org/2001/XMLSchema-instance}schemaLocation": "http://www.phyloxml.org http://www.phyloxml.org/1.00/phyloxml.xsd"},
        E.phylogeny(
            {"rooted":"true"},
        ),
        E.taxonomies(
            *(
                E.taxonomy(
                    E.color(tax["color"]),
                    code=tax["code"],
                )
                for tax in taxa_colors.values()
            )
        )
    )

    known_names = set(taxid_name_conv.keys())
    missing_names = set()

    names = []
    phylo = my_doc.find("./phylogeny", NS)
    cursor = phylo
    name = None
    going_down = True
    cur_id = 0
    species_count = 0
    for tok in tokens.finditer(newick):
        m = tok.group(0)
        if m == ")" or m == ",":
            if name in taxa_colors:
                tax = ET.SubElement(cursor, "taxonomy")
                ET.SubElement(tax, "code").text = taxa_colors[name]["code"]
                ET.SubElement(cursor, "name").text = name
            elif going_down:
                ET.SubElement(cursor, "name").text = name

            if going_down:
                # leaf node, put id
                species_count += 1
                lname = name.lower()
                if lname not in taxid_name_conv:
                    missing_names.add(name)
                    node_id = f"unknown_{cur_id}"
                    cur_id += 1
                else:
                    node_id = taxids[taxid_name_conv[lname]]
                    known_names.remove(lname)

                ET.SubElement(cursor, "id").text = node_id
                names.append(name)

                going_down = False

            cursor = cursor.getparent()

            if m == ")":
                continue

        if m == "(" or m == ",":
            cursor = ET.SubElement(cursor, "clade")
            going_down = True
            continue

        if m == ";":
            assert cursor == phylo, "incorrect newick file"
            break
        else:
            name = m.replace("_", " ").strip()
    ET.SubElement(phylo, "name").text = "Phylogenetic tree"
    ET.SubElement(phylo, "description").text = f"{level.capitalize()}, {species_count} species"

    if missing_names:
        print(f"Import for {level}:")
        missing_names_str = ', '.join(f'"{n}"' for n in missing_names)
        print(f"Unmatched names in newick file: {missing_names_str}")
        unused_names_str = ', '.join(f'"{taxid_name_conv[n]}"' for n in known_names)
        print(f"Unused names from orthodb: {unused_names_str}")
        # exit()


    ET.ElementTree(
        my_doc,
        parser=ET.XMLParser(remove_blank_text=True),
    ).write(phyloxml_file, xml_declaration=True, encoding="ASCII")

def main():
    cwd = Path(__file__).parent.absolute()
    newick = cwd / "newick"
    data = cwd.parent /"app"/"phyloxml"

    convert(
        str(newick/"phyloT_vertebrata_newick.txt"),
        str(data/"4_Vertebrata.xml"),
        "Vertebrata",
        taxa_colors={
            "Mammalia": {
                "code": "mam",
                "color": "0x40FF00",
            }
        }
    )
    convert(
        str(newick/"phyloT_Eukaryota-full_newick.txt"),
        str(data/"2_Eukaryota_Eukaryota (all species).xml"),
        "Eukaryota",
        taxa_colors={
            "Mammalia": {
                "code": "mam",
                "color": "0x06d6a0",
            },
            "Ecdysozoa": {
                "code": "ecd",
                "color": "0xee6c4d",
            },
            "Viridiplantae": {
                "code": "vir",
                "color": "0xef476f",
            },
            "Protista": {
                "code": "pro",
                "color": "0x073b4c",
            },
            "Actinopterygii": {
                "code": "act",
                "color": "0x118ab2",
            },
            "Fungi": {
                "code": "fun",
                "color": "0xb5179e",
            },
            "Sauropsida": {
                "code": "sau",
                "color": "0xb98b73",
            }

        }
    )
    convert(
        str(newick/"phyloT_Eukaryota_newick.txt"),
        str(data/"1_Eukaryota_Eukaryota (compact).xml"),
        "Eukaryota",
        taxa_colors={
            "Mammalia": {
                "code": "mam",
                "color": "0x40FF00",
            }
        }
    )
    convert(
        str(newick/"phyloT_Protista_newick.txt"),
        str(data/"8_Protista.xml"),
        "Protista",
        taxa_colors={

            }

    )
    convert(
        str(newick/"phyloT_Viridiplantae_newick.txt"),
        str(data/"11_Viridiplantae.xml"),
        "Viridiplantae",
        taxa_colors={

            }

    )
if __name__ == "__main__":
    main()