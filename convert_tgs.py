#!/usr/bin/python3
import os, sys
import lottie as tgs
from lottie.exporters import gif
path = sys.argv[1]
a=tgs.parsers.tgs.parse_tgs(path)
path2 = path.replace('.tgs', '.gif')
with open(path2, 'wb') as f:
    gif.export_gif(a, f)

