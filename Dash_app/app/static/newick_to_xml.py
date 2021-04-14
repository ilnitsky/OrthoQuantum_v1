import sys
from pathlib import Path

from lxml import etree as ET

XML_HEADER="""<?xml version="1.0" encoding="UTF-8"?>
<phyloxml xmlns="http://www.phyloxml.org" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.phyloxml.org http://www.phyloxml.org/1.00/phyloxml.xsd">
<phylogeny rooted="true">
    <name>demo tree</name>
    <description>tree test</description>
"""

# TODO: create xml with the proper xml parser
tr_table = {
    "(": "<clade>",
    ",": "</clade><clade>",
    ")": "</clade>",
    ";": "</phylogeny></phyloxml>",
}


def main():
    if len(sys.argv) != 4:
        raise RuntimeError("1 argument: path to newick file")
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    txt_path = Path(sys.argv[3])

    newick = in_path.read_text().strip()
    # id_counter = 0
    with out_path.open("w") as f:
        f.write(XML_HEADER)
        in_name = False
        for char in newick:
            if char in tr_table:
                if in_name:
                    in_name = False
                    f.write("</name>")
                    # f.write(f"<id>{id_counter}</id>")
                    # id_counter += 1
                f.write(tr_table[char])
            else:
                if not in_name:
                    f.write("<name>")
                    in_name = True
                f.write(char)



    # ET.register_namespace("", "http://www.phyloxml.org")
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    NS = {
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "": "http://www.phyloxml.org"
    }
    out_str = str(out_path.resolve())
    tree = ET.parse(
        out_str,
        ET.XMLParser(remove_blank_text=True)
    )
    root = tree.getroot()

    for name_node in root.iterfind(".//name", NS):
        new_name = name_node.text.replace("_", " ").strip()
        if new_name == "Cebus imitator":
            new_name = "Cebus capucinus imitator"
        name_node.text = new_name

    # pre-strip
    with txt_path.open("r") as f:
        lines = f.readlines()

    name_2_id = {}
    for i in range(len(lines)):
        name = lines[i].strip()
        lines[i] = name
        name_2_id[name] = str(i)

    with txt_path.open("w") as f:
        f.write('\n'.join(lines))


    for clade_node in root.iterfind(".//clade", NS):
        if clade_node.find("./clade", NS) is not None:
            continue
        el = ET.Element("id")
        el.text = name_2_id[clade_node.find("./name", NS).text]
        clade_node.append(el)

    # from IPython import embed; embed()
    tree.write(out_str, xml_declaration=True)



if __name__ == "__main__":
    main()