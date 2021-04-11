import sys
from pathlib import Path
import random

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
    if len(sys.argv) != 3:
        raise RuntimeError("1 argument: path to newick file")
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

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



    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    # ET.register_namespace("", "http://www.phyloxml.org")
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

    id_counter = 1
    for node in root.iterfind(".//clade", NS):
        if node.find("./clade", NS) is not None:
            continue
        el = ET.Element("id")
        el.text = str(id_counter)
        id_counter += 1
        node.append(el)

    # from IPython import embed; embed()
    tree.write(out_str, xml_declaration=True)

    # TODO: This will be done at runtime, in response to user request
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(out_str, parser)
    root = tree.getroot()
    graphs = ET.SubElement(root, "graphs")
    graph = ET.SubElement(graphs, "graph", type="heatmap")
    ET.SubElement(graph, "name").text = "Heatmap test"
    legend = ET.SubElement(graph, "legend", show="1")

    legend_names = [f"PROT_{i}" for i in range(0, 100)]
    for ln in legend_names:
        field = ET.SubElement(legend, "field")
        ET.SubElement(field, "name").text = ln

    gradient = ET.SubElement(legend, "gradient")
    ET.SubElement(gradient, "name").text = "Custom"
    ET.SubElement(gradient, "classes").text = "2"

    ###

    data = ET.SubElement(graph, "data")
    for id_node in root.iterfind(".//id", NS):
        values = ET.SubElement(data, "values", {"for":id_node.text})
        for _ in legend_names:
            ET.SubElement(values, "value").text = random.choice(("0", "100"))

    tree.write(out_str, xml_declaration=True)


if __name__ == "__main__":
    main()