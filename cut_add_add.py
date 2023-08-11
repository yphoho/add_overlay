#!/usr/bin/python3
# -*- coding: utf-8 -*-
# yang @ 2023-08-12 13:40:20

import sys
import os


indir = './'
outdir = './gopro/dashboard/'
fit_file = 'none'

os.system('mkdir -p %s' % outdir)

for line in open('timeline.txt'):
    line = line.strip()

    if line == '' or line[0] == '#': continue

    if line.startswith('indir'):
        indir = line.split('=')[1]
        continue
    elif line.startswith('fit_file'):
        fit_file = line.split('=')[1]
        continue

    infile, start, end, xx = line.split()

    infile_with_dir = os.path.join(indir, infile)
    outfile = outdir + infile + '-' + start + '.mp4'

    if os.path.exists(outfile): continue

    ss = 'gopro-cut.py --start %s --end %s %s %s' % (start, end, infile_with_dir, outfile)
    print(ss)
    if os.system(ss) != 0:
        sys.exit(0)

    if xx != 'no':
        ss = './add_overlay.sh %s %s' % (outfile, fit_file)
        print(ss)
        os.system(ss)
