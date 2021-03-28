import io
import base64
import os

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Output, Input

import numpy as np
import pandas as pd
from pandas import DataFrame, read_csv
from astropy.table import Table, Column
from SPARQLWrapper import SPARQLWrapper, JSON
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib
import plotly.graph_objects as go

from PIL import Image, ImageChops
from Bio.Blast.NCBIWWW import qblast
from Bio.Blast import NCBIXML
from Bio import SeqIO
import urllib.request, urllib.error, urllib.parse
import subprocess
## Navbar
from navbar import Navbar

nav = Navbar()

df = pd.read_csv("SPARQLWrapper.csv")

ogcsv_data = read_csv('OG.csv', sep=';')
OG_list = ogcsv_data['label']
OG_names = ogcsv_data['Name']
UniProt_AC = ogcsv_data['UniProt_AC']
OG_list = [x.strip() for x in OG_list]
#
# with open("assets/data/genes.csv") as gene:
# Temp = read_csv('assets/data/genes.csv', sep='`;')['UniProt AC (mouse)']

taxid_species = read_csv('assets/data/taxid-species.csv', sep=',')
Sp_name = taxid_species['name']
Taxid = taxid_species['taxid']

# def blast_query(seq_fasta, entrez):

#     blast_results = open("qblast_blastn.out")
#     blast_records = NCBIXML.parse(blast_results)
#     for blast_rec in blast_records:
#         for alignment in blast_rec.alignments:
#             for hsp in alignment.hsps:
#                 print(hsp.score, hsp.expect)


def fasta_from_row():
    df = pd.read_csv("OG.csv")

    iOG = ['196631at7742', '215143at7742']

    strng = ''
    for i in iOG:
        strng = strng + 'odbgroup:' + str(i) + ', '
    strng = strng[:-2]

    query = """
    prefix : <http://purl.orthodb.org/>
    select
    distinct ?org_name ?xref ?description ?og
    where {
    ?gene a :Gene.
    ?gene :name ?Gene_name.
    ?gene up:organism/a ?taxon.
    ?taxon up:scientificName ?org_name.
    ?gene :xref [a :Xref; :xrefResource ?xref]. ?xref a :Uniprot.
    ?gene :description ?description; :memberOf  ?og.
    filter (?og in (%s))
    }
    GROUP BY ?org_name
    ORDER BY ?og
    """ % (strng)

    endpoint.setQuery(query)
    endpoint.setReturnFormat(JSON)
    results.append(endpoint.query().convert())

    col = ["org_name", "xref", "description", "og"]

    og_info = [[]]

    for p in results:
        for res in p["results"]["bindings"]:
            og_info_row = []
            for k in col:
                og_info_row.append(res[k]["value"])
            og_info.append(og_info_row)

    og_info_df = pd.DataFrame(og_info, columns=col)


class Ortho_Group(object):
    def __init__(self, og_name, SubmittedProt_ID, SubmittedProt_Fasta):
        self.og_name = og_name
        self.SubmittedProt_ID = SubmittedProt_ID

        self.SubmittedProt_Fasta = SubmittedProt_Fasta

    def absent_in_species(self, dataframe, og_name):
        # for col_name in column_names:
        species_with_0 = dataframe.loc[dataframe[og_name] == 0.0]
        self.species_w_0 = species_with_0['Organisms'].tolist()

    def make_taxid(self):
        Tax_dict = dict(zip(Sp_name, Taxid))
        self.taxid = []
        for i in self.species_w_0:
            self.taxid.append(Tax_dict[i])
        with open('assets/data/new.txids', 'w') as f:
            for item in self.taxid:
                f.write("%s\n" % item)

    def load_fasta(self):
        handle_list = []
        id_list = [self.SubmittedProt_ID]
        print(self.SubmittedProt_ID)
        for id in id_list:
            handle = urllib.request.urlopen("http://www.uniprot.org/uniprot/{}.fasta".format(id))
            F = handle.read().decode('utf-8')
            print(str(F))
            handle_list.append(str(F))
        self.SubmittedProt_Fasta = F
        with open('assets/data/og.fa', 'w') as f:
            f.write(str(F))

    def blast_in_absent(self):
        # TODO: Путь вне репозитория, этот скриптик бы сюда...
        rc = subprocess.call("/home/ken/nr/blast.sh")


my_og = Ortho_Group(OG_names[0], UniProt_AC[0], 'gg')
my_og.absent_in_species(df, my_og.og_name)
my_og.make_taxid()
my_og.load_fasta()
my_og.blast_in_absent()

print(my_og.species_w_0)
