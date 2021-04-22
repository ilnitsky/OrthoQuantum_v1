import re
from pathlib import Path
from lxml import etree as ET
from lxml.builder import ElementMaker

tokens = re.compile(r"[^(),;]+|\(|\)|,|;")

def convert(newick_file, phyloxml_file, txt_file, name_replacements={}, taxa_colors={}):
    with open(newick_file) as f:
        newick = f.read().strip()

    with open(txt_file) as f:
        lines = f.readlines()

    name_2_id = {}
    for i in range(len(lines)):
        name = lines[i].strip()
        lines[i] = name
        name_2_id[name] = str(i)

    with open(txt_file, "w") as f:
        f.write('\n'.join(lines))

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

    phylo = my_doc.find("./phylogeny", NS)
    cursor = phylo
    name = None
    going_down = True
    for tok in tokens.finditer(newick):
        m = tok.group(0)
        if m == ")" or m == ",":
            ET.SubElement(cursor, "name").text = name
            if going_down:
                # leaf node, put id
                ET.SubElement(cursor, "id").text = name_2_id[name]
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
            name = name_replacements.get(name, name)

    # print(ET.tostring(my_doc, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode())
    ET.ElementTree(
        my_doc,
        parser=ET.XMLParser(remove_blank_text=True),
    ).write(phyloxml_file, xml_declaration=True, encoding="UTF-8")


def main():
    cwd = Path(__file__).parent.absolute()
    newick = cwd / "newick"
    data = cwd.parent /"app"/"app"/"assets"/"data"
    phyloxml = data/"phyloxml"

    convert(
        str(newick/"phyloT_vertebrata_newick.txt"),
        str(phyloxml/"Vertebrata.xml"),
        str(data/"Vertebrata.txt"),
        name_replacements={
            "Cebus imitator": "Cebus capucinus imitator",
        },
        taxa_colors={
            "Mammalia": {
                "code": "mam",
                "color": "0x40FF00",
            }
        }
    )


if __name__ == "__main__":
    main()