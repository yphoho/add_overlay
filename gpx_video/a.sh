#!/bin/sh -x
set -e
set -u

cd `dirname $0`


gpx_file=haihedonglu.fit
# gpx_file="t1.fit t2.fit"
# gpx_file=tuanpohu.fit
# gpx_file=miaofengshan.gpx

outfile="../gopro/$gpx_file.mp4"
rm -f "$outfile"

# width=1920
# height=1080
width=960
height=540

## bluemarble,osm,stamen-terrain,stamen-terrain-background,stamen-terrain-lines,stamen-toner,stamen-toner-lite,stamen-watercolor,thunderforest-cycle

provider=gaode-map
# provider=esri-world-imagery
# provider=osm
# provider=google-map
# provider=google-map-satellite-with-label
# provider=stamen-toner
# provider=stamen-toner-lite

audio_file=`find ./audio/ -type f | shuf | tail -n1`

./gpx_to_route.py "$@" -s $width $height -p $provider --audio "$audio_file" --photo ./p.txt $gpx_file "$outfile"
# ./gpx_to_route.py "$@" --auto-orientation -s $width $height -p $provider --audio "$audio_file" --photo ./p.txt $gpx_file "$outfile"
