
from future import standard_library
standard_library.install_aliases()
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
import io 
from builtins import str
from past.utils import old_div
import base64
import os
import wand
# import warnings
# warnings.simplefilter("ignore")
from PIL import Image, ImageChops
from bioservices import UniProt


import requests 
from Bio import SeqIO
from io import StringIO
import urllib3
import urllib
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import certifi

taxonomy = 'Ven'
taxonomy1 = str(taxonomy.split('-')[0])
print(taxonomy1)