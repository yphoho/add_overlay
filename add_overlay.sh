#!/bin/sh -x
set -e
set -u


cd `dirname $0`

infile=$1

if [ $# -gt 1 ]; then
    fit_file=$2
else
    fit_file=none
fi


outfile=${infile}-dashboard.mp4

# gpx_mode=EXTEND
gpx_mode=OVERWRITE


## gopro-dashboard.py --include date_and_time big_mph gradient_chart gradient altitude temperature cadence --units-speed kph ./gopro/s30.mp4 ./gopro/s30-dashboard.mp4


## gopro-dashboard.py --double-buffer --layout xml --layout-xml ./layouts/my-layout.xml --units-speed kph --units-distance km ./gopro/s30.mp4 ./gopro/s30-dashboard.mp4

## gopro-dashboard.py --double-buffer --profile nnvgpu --layout xml --layout-xml ./layouts/my-layout.xml --units-speed kph --units-distance km ./gopro/s30.mp4 ./gopro/s30-dashboard.mp4


# gopro-cut.py --start 00:03:00.000000 --end 00:04:00 ./gopro/garden/GH020056.MP4 ./gopro/s60.mp4


if [ $fit_file = 'none' ]; then
    gopro-dashboard.py --include date_and_time big_speed map moving_journey_map --layout xml --layout-xml ./layouts/my-layout.xml --units-speed kph --units-distance km $infile $outfile
else
    gopro-dashboard.py --layout xml --layout-xml ./layouts/my-layout.xml --units-speed kph --units-distance km --gpx-merge $gpx_mode --fit $fit_file $infile $outfile
fi
