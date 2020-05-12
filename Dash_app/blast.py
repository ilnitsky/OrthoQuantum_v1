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
import cStringIO
import base64
import os
from PIL import Image, ImageChops
from Bio.Blast.NCBIWWW import qblast
from Bio.Blast import NCBIXML
from Bio import SeqIO
import urllib2

## Navbar
from navbar import Navbar

nav = Navbar()


df = pd.read_csv("SPARQLWrapper.csv")

with open("OG.csv") as OGS:
    OG_list = read_csv('OG.csv', sep=';')['label']
    OG_names = read_csv('OG.csv', sep=';')['Name']
    UniProt_AC = read_csv('OG.csv', sep=';')['UniProt_AC']
OG_list = [x.strip() for x in OG_list]

with open("genes.csv") as OGS:
    Temp = read_csv('genes.csv', sep=';')['UniProt AC (mouse)']
# OG_list = [x.strip() for x in OG_list]


def blast_query(seq_fasta, entrez):
    result_handle = qblast("blastp", "refseq_genomic", "P05480.fasta", format_type = "XML", entrez_query = "txid94835[organism] OR txid8502[organism] OR txid143302[organism] OR txid9606[organism]"
    #  entrez_query='{}'.format(entrez)
    )
    save_file = open("qblast_blastn.out", "w")
    save_file.write(result_handle.read())
    save_file.close()
    result_handle.close() 

    blast_results = open("qblast_blastn.out")
    blast_records = NCBIXML.parse(blast_results)
    for blast_rec in blast_records:
        for alignment in blast_rec.alignments:
            for hsp in alignment.hsps:
                print hsp.score, hsp.expect

    

def load_fasta(id_list):
    handle_list = []
    i = 0
    for id in id_list:
        handle = urllib2.urlopen("http://www.uniprot.org/uniprot/{}.fasta".format(id))
        F = handle.read()
        handle_list.append(str(F))
        print F
        i = i + 1
        
    return handle_list

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

    col = ["org_name", "xref", "description",  "og"]        

    og_info = [[]]

    for p in results:
        for res in p["results"]["bindings"]:
            og_info_row = []  
            for k in col:
                og_info_row.append(res[k]["value"])        
            og_info.append(og_info_row)
       
    og_info_df = pd.DataFrame(og_info, columns=col)

og_name = OG_names[7]
uniprot_name = UniProt_AC[7]

class Ortho_Group():
    def __init__(self, og_name, SubmittedProt_ID, SubmittedProt_Fasta):
        self.og_name = og_name
        self.SubmittedProt_ID = UniProt_AC

        self.SubmittedProt_Fasta = SubmittedProt_Fasta

    def absent_in_species(self, dataframe, og_name):
        # for col_name in column_names:
        species_with_0 = dataframe.loc[dataframe[og_name] == 0.0]
        self.species_w_0 = species_with_0['Organisms'].tolist()
        
    def blast_in_absent(self):
        query_str = ''
        if not self.species_w_0:
            print('All species have an ortholog')
        else:
            for species in self.species_w_0:
                query_str += ' OR "' + species + '"[organism]'
            query_str = query_str.lstrip(' OR')
            evalue = 1
            percentIdent = 60
            return query_str






my_og = Ortho_Group(og_name, uniprot_name, 'gg')
my_og.absent_in_species(df, my_og.og_name)

print my_og.species_w_0
print og_name
entrez = my_og.blast_in_absent()
print entrez


Temp = Temp[:len(Temp)-46].tolist()
# seq_fasta = load_fasta([uniprot_name])[0]
seq_fasta = load_fasta(UniProt_AC)
seq_fasta = '\n'.join(seq_fasta)
# seq_fasta_file = open("P05480.fasta", "w")
# seq_fasta_file.write(seq_fasta)

# blast_query(seq_fasta_file, entrez)


# import os
# S = "blastp -query P05480.fasta -out blast_output -db nr.00"
# os.system(S) 