#!/bin/sh -x
set -e
set -u

cd `dirname $0`


origin_video=../../gopro/zhongguancun.fit-audio.mp4
clip_video=clip.mp4

input=a.png

width=540
height=960
fps=60


## cut
ffmpeg -y -hide_banner -loglevel error -i $origin_video -ss 20 -to 30 -c copy $clip_video

ffprobe -v error -select_streams v -show_entries stream=width,height -of csv=p=0:s=x $clip_video

## scale
ffmpeg -y -hide_banner -loglevel error -i $clip_video -vf "scale=$width:$height:force_original_aspect_ratio=decrease,pad=$width:$height:-1:-1:color=black" -r $fps -an -c:v libx264 -preset veryfast SmallClip.mp4
# ffmpeg -y -i $input -vf "scale='min(1280,iw)':min'(720,ih)':force_original_aspect_ratio=decrease,pad=1280:720:-1:-1:color=black" output.2.jpg
# ffmpeg -y -i $input -vf "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720" output.3.jpg

# ## ffmpeg -f concat -i concat.txt -an -c:v libx264 -crf 23 -fflags +genpts video.mp4
# ffmpeg -y -hide_banner -loglevel info -f concat -i concat.txt -an -c:v libx264 -preset veryfast ../../gopro/concat.mp4
#
# # ffmpeg -y -hide_banner -loglevel error -i video.mp4 -i main.mp4 -shortest -map 0:v -map 1:a -c copy Final.mp4


## one image to video
ffmpeg -y -hide_banner -loglevel error -loop 1 -i $input -vf "scale=$width:$height:force_original_aspect_ratio=decrease,pad=$width:$height:-1:-1:color=black" -t 10 -r $fps -c:v libx264 -preset veryfast one_image.mp4

## series of images, and the images vary in size
# ffmpeg -i $input -vf "scale=1280:720:force_original_aspect_ratio=decrease:eval=frame,pad=1280:720:-1:-1:color=black" output
