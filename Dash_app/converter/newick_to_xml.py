import re
from pathlib import Path
from lxml import etree as ET
from lxml.builder import ElementMaker

tokens = re.compile(r"[^(),;]+|\(|\)|,|;")

def convert(newick_file, phyloxml_file, txt_file, taxa_colors={}):
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
            E.name("demo tree"),
            E.description("tree test"),
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
    names = []
    phylo = my_doc.find("./phylogeny", NS)
    cursor = phylo
    name = None
    going_down = True
    cur_id = 0
    for tok in tokens.finditer(newick):
        m = tok.group(0)
        if m == ")" or m == ",":
            ET.SubElement(cursor, "name").text = name
            if going_down:
                # leaf node, put id
                ET.SubElement(cursor, "id").text = str(cur_id)
                names.append(name)
                cur_id += 1

                going_down = False
            if name in taxa_colors:
                tax = ET.SubElement(cursor, "taxonomy")
                ET.SubElement(tax, "code").text = taxa_colors[name]["code"]

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

    # print(ET.tostring(my_doc, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode())
    ET.ElementTree(
        my_doc,
        parser=ET.XMLParser(remove_blank_text=True),
    ).write(phyloxml_file, xml_declaration=True, encoding="ASCII")

    with open(txt_file, "w") as txtfile:
        txtfile.write('\n'.join(names))


def main():
    cwd = Path(__file__).parent.absolute()
    newick = cwd / "newick"
    data = cwd.parent /"app"/"app"/"assets"/"data"
    phyloxml = data/"phyloxml"

    convert(
        str(newick/"phyloT_vertebrata_newick.txt"),
        str(data/"Vertebrata.xml"),
        str(data/"Vertebrata.txt"),
        taxa_colors={
            "Mammalia": {
                "code": "mam",
                "color": "0x40FF00",
            }
        }
    )
    convert(
        str(newick/"phyloT_Eukaryota-full_newick.txt"),
        str(data/"Eukaryota-full.xml"),
        str(data/"Eukaryota-full.txt"),
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
        str(data/"Eukaryota.xml"),
        str(data/"Eukaryota.txt"),
        taxa_colors={
            "Mammalia": {
                "code": "mam",
                "color": "0x40FF00",
            }
        }
    )
    convert(
        str(newick/"phyloT_Protista_newick.txt"),
        str(data/"Protista.xml"),
        str(data/"Protista.txt"),
        taxa_colors={
           
            }
        
    )
    convert(
        str(newick/"phyloT_Viridiplantae_newick.txt"),
        str(data/"Viridiplantae.xml"),
        str(data/"Viridiplantae.txt"),
        taxa_colors={
           
            }
        
    )
if __name__ == "__main__":
    main()