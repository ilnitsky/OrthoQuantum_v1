# 
# from PIL import Image, ImageChops

# 
# im1 = Image.open('/home/ken/best_repository_ever/Dash_app/assets/images/Vertebrata.png')
# im2 = Image.open('/home/ken/best_repository_ever/Dash_app/assets/images/Vertebrata.png')
# 
# print(type(im1))
# im2 = trim(im2)
# 
# new_height = 4140
# new_width_im1  = new_height * im1.width / im1.height
# new_width_im2  = new_height * im2.width / im2.height
# 
# im1 = im1.resize((int(new_width_im1), int(new_height)), Image.ANTIALIAS)
# im2 = im2.resize((int(new_width_im2), int(new_height)), Image.ANTIALIAS)
# 
# dst = Image.new('RGB', (im1.width + im2.width, min(im1.height, im2.height)))
# dst.paste(im1, (0, 0))
# dst.paste(im2, (im1.width, (im1.height - im2.height) // 2))
# print(dst)

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
import warnings
warnings.simplefilter("ignore")
from PIL import Image, ImageChops, ImageOps
import cv2
import subprocess

rc = subprocess.call("/home/ken/best_repository_ever/Dash_app/imagemagick.sh")
# sns.set()




def concat_phylo(im1, im2):
    im1 = Image.open(im1)
    im2 = Image.open(im2)
    new_height = 4140
    new_width_im1  = old_div(new_height * im1.width, im1.height)
    new_width_im2  = old_div(new_height * im2.width, im2.height)

    im1 = im1.resize((new_width_im1, new_height), Image.ANTIALIAS)
    im2 = im2.resize((new_width_im2, new_height), Image.ANTIALIAS)

    dst = Image.new('RGB', (im1.width + im2.width, min(im1.height, im2.height)))
    dst.paste(im1, (0, 0))
    dst.paste(im2, (im1.width, (im1.height - im2.height) // 2))
    return dst


    # ax.tick_params(labeltop=True)
    
    
# # if os.path.isfile("Presence-Vector.csv") == True:
#     os.remove("Presence-Vector.csv")

# if os.path.isfile('/home/ken/best_repository_ever/Dash_app/assets/images/concat_phylo.png') == True:
    # os.remove('/home/ken/best_repository_ever/Dash_app/assets/images/concat_phylo.png')
# 
# 
# plt.savefig('/home/ken/best_repository_ever/Dash_app/assets/images/Presence.png')

concat_phylo('/home/ken/best_repository_ever/Dash_app/assets/images/Vertebrata.png', '/home/ken/best_repository_ever/Dash_app/assets/images/out.png').save('/home/ken/best_repository_ever/Dash_app/assets/images/concat_phylo.png')
 
 