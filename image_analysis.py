from Astro import Exposure
import os
from matplotlib import pyplot as plt


images = [im for im in os.listdir() if ".CR3" in im]
e = Exposure(images[0])
e.load_all()