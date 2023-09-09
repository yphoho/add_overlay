#!/bin/sh -x
set -e
set -u

cd `dirname $0`


# gpx_file=tuanpohu.fit
gpx_file=tuanpohu.gpx
# gpx_file=haidiangongyuan.gpx
# gpx_file=zhongguancun.gpx

outfile=../gopro/$gpx_file.mp4
rm -f $outfile

# bluemarble,osm,stamen-terrain,stamen-terrain-background,stamen-terrain-lines,stamen-toner,stamen-toner-lite,stamen-watercolor,thunderforest-cycle

# width=1920
# height=1080
width=540
height=960

./gpx_to_route.py -s $width $height -p osm --photo `ls -m ./photo/* | tr '\n' ' ' | sed 's/ //g'` $gpx_file $outfile

# ./gpx_to_route.py -s $width $height -p stamen-toner $gpx_file $outfile
# ./gpx_to_route.py -s $width $height -p stamen-toner-lite $gpx_file $outfile

# ./gpx_to_route.py -s $width $height -p stamen-terrain $gpx_file $outfile
# ./gpx_to_route.py -s $width $height -p stamen-terrain-background $gpx_file $outfile
# ./gpx_to_route.py -s $width $height -p stamen-terrain-lines $gpx_file $outfile

## ./gpx_to_route.py -s $width $height -p stamen-watercolor $gpx_file $outfile
## ./gpx_to_route.py -s $width $height -p bluemarble $gpx_file $outfile


audio_file=`ls ./audio/freepd/*.mp3 | shuf | tail -n1`
outfile_with_audio=../gopro/$gpx_file-audio.mp4
rm -f $outfile_with_audio

ffmpeg -y -hide_banner -loglevel error -i $outfile -i "$audio_file" -c:v copy -c:a aac -shortest $outfile_with_audio
