import csv
import json
import re
from pathlib import Path
from lxml import etree as ET
from lxml.builder import ElementMaker
import SPARQLWrapper

import prottree_species_data
import csv

tokens = re.compile(r"[^(),;]+|\(|\)|,|;")

def convert_to_new(old_dict):
    for k in list(old_dict.keys()):
        old_dict[k] = old_dict[k]["color"]
    print(json.dumps(old_dict, indent=4))

def process_colors(colors):
    res = {}
    codes = set()
    for name, color in colors.items():
        try:
            if isinstance(color, str):
                color = int(color, 16)
            elif not isinstance(color, int):
                raise ValueError("Color must be int or str")
            assert 0 < color < 0xFFFFFF, "Color is out of range"

            code = name[:3].lower()
            if code in codes:
                i = 0
                code_cand = f"{code}_{i}"
                while code_cand in codes:
                    i+=1
                    code_cand = f"{code}_{i}"
                code = code_cand
            codes.add(code)
            res[name] = {
                "code": code,
                "color": f"0x{color:06X}",
            }

        except Exception as e:
            raise RuntimeError(f"Error while processing {name}") from e
    return res


def convert(newick_file, phyloxml_file, level, taxa_colors={}):
    taxa_colors = process_colors(taxa_colors)
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


def convert_panther(newick_file, phyloxml_file, prot_tree_file, colors):
    colors = process_colors(colors)
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
                for tax in colors.values()
            )
        )
    )

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
            if name in colors:
                tax = ET.SubElement(cursor, "taxonomy")
                ET.SubElement(tax, "code").text = colors[name]["code"]
                ET.SubElement(cursor, "name").text = name
            elif going_down:
                ET.SubElement(cursor, "name").text = name

            if going_down:
                # leaf node, put id
                species_count += 1

                cur_id += 1
                ET.SubElement(cursor, "id").text = str(cur_id)

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

    ET.SubElement(phylo, "name").text = "Gene tree" # TODO: correct name
    ET.SubElement(phylo, "description").text = f""


    ET.ElementTree(
        my_doc,
        parser=ET.XMLParser(remove_blank_text=True),
    ).write(phyloxml_file, xml_declaration=True, encoding="ASCII")

    pantherID_2_name = prottree_species_data.species_data
    name_2_id = dict((name, i) for i, name in enumerate(names, 1))

    assert len(name_2_id) == len(pantherID_2_name), "can't translate"
    assert set(name_2_id.keys()) == set(pantherID_2_name.values()), "can't translate"


    with open(prot_tree_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(("Genome", "TreeID"))
        for pantherID, name in pantherID_2_name.items():
            writer.writerow((pantherID, name_2_id[name]))


def main():
    cwd = Path(__file__).parent.absolute()
    newick = cwd / "newick"
    panther = cwd / "panther"
    data = cwd.parent /"app"/"phyloxml"

    convert_panther(
        str(panther/"phyloT_PANTHER_newick.txt"),
        str(panther/'panther'/"PANTHER.xml"),
        str(panther/'panther'/"prottree_id_converter.csv"),
        colors={
            "Bacteria": 0xc6b1b2,
            "Mammalia": 0x06d6a0,
            "Sauropsida": 0xb98b73,
            "Cnidaria": 0xb8f2e6,
            "Actinopterygii": 0x118ab2,
            "Nematoda": 0xaed9e0,
            "Arthropoda": 0xee6c4d,
            "Insecta": 0xee6c4d,
            "Arachnida": 0xf5a693,
            "Basidiomycota": 0x8342a0,
            "Ascomycota": 0x6c3dbe,
            "Chlorophyta": 0x4dedd5,
            "asterids": 0x32e875,
            "rosids": 0x32e875,
            "Liliopsida": 0x32e875,
            "Discoba": 0x8d99ae,
            "Sar": 0x7e220c,
            "Metamonada": 0xb7b7a4,
            "Amoebozoa": 0x9c6644,
            "Archaea": 0x493657,
        }

    )
    convert(
        str(newick/"phyloT_vertebrata_newick.txt"),
        str(data/"4_Vertebrata.xml"),
        "Vertebrata",
        taxa_colors={
            "Mammalia": 0x40FF00,
            "Aves": 0xb98b73,
            "Actinopterygii": 0x118ab2,
        }
    )
    convert(
        str(newick/"phyloT_Eukaryota-full_newick.txt"),
        str(data/"2_Eukaryota_Eukaryota (all species).xml"),
        "Eukaryota",
        taxa_colors={
            "Mammalia": 0x06d6a0,
            "Nematoda": 0xaed9e0,
            "Arthropoda": 0xee6c4d,
            "Protista": 0x073b4c,
            "Actinopterygii": 0x118ab2,
            "Sauropsida": 0xb98b73,
            "Apicomplexa": 0xcb997e,
            "Ciliophora": 0xddbea9,
            "Stramenopiles": 0x6b705c,
            "Cnidaria": 0xb8f2e6,
            "Lophotrochozoa": 0xaed9e0,
            "Metamonada": 0xb7b7a4,
            "Amoebozoa": 0x9c6644,
            "Basidiomycota": 0x8342a0,
            "Ascomycota": 0x6c3dbe,
            "Chlorophyta": 0x4dedd5,
            "Streptophyta": 0x32e875,
            "Rhodophyta": 0x006d77,
            "Discoba": 0x8d99ae,
            "Fungi incertae sedis": 0xb5838d,
        }
    )
    convert(
        str(newick/"phyloT_Eukaryota_newick.txt"),
        str(data/"1_Eukaryota_Eukaryota (compact).xml"),
        "Eukaryota",
        taxa_colors={
            "Mammalia": 0x06d6a0,
            "Aves": 0xb98b73,
            "Cnidaria": 0xb8f2e6,
            "Actinopterygii": 0x118ab2,
            "Basidiomycota": 0x8342a0,
            "Ascomycota": 0x6c3dbe,
            "Chlorophyta": 0x4dedd5,
            "Streptophyta": 0x32e875,
            "Rhodophyta": 0x006d77,
            "Nematoda": 0xaed9e0,
            "Insecta": 0xee6c4d,
            "Arachnida": 0xf5a693,
            "Sar": 0x7e220c,
        }
    )
    convert(
        str(newick/"phyloT_Protista_newick.txt"),
        str(data/"8_Protista.xml"),
        "Protista",
        taxa_colors={
            "Apicomplexa": 0xcb997e,
            "Ciliophora": 0xddbea9,
            "Stramenopiles": 0x6b705c,
            "Metamonada": 0xb7b7a4,
            "Amoebozoa": 0x9c6644,
            "Discoba": 0x8d99ae,
        }

    )
    convert(
        str(newick/"phyloT_Viridiplantae_newick.txt"),
        str(data/"11_Viridiplantae.xml"),
        "Viridiplantae",
        taxa_colors={
            "Chlorophyta": 0x4dedd5,
            "Streptophyta": 0x32e875,
            "Rhodophyta": 0x006d77,
        }
    )    
    convert(
        str(newick/"phyloT_Fungi_newick.txt"),
        str(data/"9_Fungi.xml"),
        "Fungi",
        taxa_colors={
            "Basidiomycota": 0x8342a0,
            "Ascomycota": 0x6c3dbe,
            "Fungi incertae sedis": 0xb5838d,
        }
    )
    convert(
        str(newick/"phyloT_Metazoa_newick.txt"),
        str(data/"3_Metazoa.xml"),
        "Metazoa",
        taxa_colors={
            "Mammalia": 0x06d6a0,
            "Aves": 0xb98b73,
            "Nematoda": 0xaed9e0,
            "Arthropoda": 0xee6c4d,
            "Actinopterygii": 0x118ab2,
            "Cnidaria": 0xb8f2e6,
            "Lophotrochozoa": 0xaed9e0,
        }
    )    

if __name__ == "__main__":
    main()