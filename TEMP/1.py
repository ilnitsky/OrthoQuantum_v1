from PIL import Image, ImageChops

def trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0,0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)

im = Image.open("Presence.png")
im = trim(im)
im.show()







 for Y in n["results"]["bindings"]:

                og_Y_list = []
                og_Y = Y["og"]["value"].split('/')[-1]
                og_Y_list.append(og_Y)
                Q.append(uniprot_ac_i)
                L.append(uniprot_name_i)
                M.append(og_Y_list[0])

            results.append(endpoint.query().convert())
            results = results
        
        uniprot_df = pd.DataFrame(columns = ['label','Name', 'PID'])
        data_tuples = list(zip(M,L,Q))
        uniprot_df = pd.DataFrame(columns = ['label','Name', 'PID'], data = data_tuples)

        uniprot_df['is_duplicate'] = uniprot_df.duplicated(subset='label')
        print(uniprot_df)
        
        J = []
        K = []
        P = []
        for row in uniprot_df.itertuples(index=True, name='Pandas'):
            if row.is_duplicate == False:
                rowlist_Name = uniprot_df[uniprot_df.label == str(row.label)].Name.tolist()
                rowlist_PID = uniprot_df[uniprot_df.label == str(row.label)].PID.tolist()
                
        #remove duplicate names
                rowlist_alpha =[]
                for i in rowlist_Name:
                    if i not in rowlist_alpha:
                        rowlist_alpha.append(i)
                

                J.append(row.label)
                K.append("-".join(rowlist_alpha))
                P.append(rowlist_PID[0])

        #SPARQL Look For Presence of OGS in Species        
        OG_list = J
        data_tuples = list(zip(J,K,P))
        uniprot_df = pd.DataFrame(columns = ['label','Name','UniProt_AC'], data = data_tuples)
        uniprot_df.to_csv('OG.csv', sep=';', index=False)
        