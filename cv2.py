from PIL import Image

im1 = Image.open('Vertebrata-tree.png')
im2 = Image.open('334.png')

print(im1.height)
print(im2.height)


width = im1.width
height = im1.height


new_height = 4140
new_width  = new_height * width / height

im1 = im1.resize((new_width, new_height), Image.ANTIALIAS)

im1.save('sompic.png') 



width = im2.width
height = im2.height

from PIL import ImageOps

border = (width/10, height/4.06, 0, 1210) # left, up, right, bottom
im2 = ImageOps.crop(im2, border)



new_height = 4140
new_width  = new_height * width / height



im2 = im2.resize((new_width, new_height), Image.ANTIALIAS)

im2.save('soic.png') 


def get_concat_h_cut_center(im1, im2):
    dst = Image.new('RGB', (im1.width + im2.width, min(im1.height, im2.height)))
    dst.paste(im1, (0, 0))
    dst.paste(im2, (im1.width, (im1.height - im2.height) // 2))
    return dst


get_concat_h_cut_center(im1, im2).save('pillow_concat_h_cut_center.png')

print(im1.height)
print(im2.height)
