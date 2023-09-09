#!/usr/bin/python3

import sys

import argparse
from datetime import datetime, timedelta
from collections import defaultdict

import subprocess

from geopy.distance import geodesic

from PIL import Image, ImageDraw, ExifTags
import geotiler

import loading


def load_gps_point(filename, num_p):
    timestamps, positions = loading.load_gps_data(filename)
    # print(timestamps[0].timestamp(), type(timestamps[0]))
    print('origin gps num:', len(positions))

    # positions = positions[int(len(positions)/2):]

    r = 1.0 * len(positions) / num_p
    new_positions = [positions[int(r*i)] for i in range(num_p)]
    new_positions.append(positions[-1])
    new_timestamps = [timestamps[int(r*i)] for i in range(num_p)]
    new_timestamps.append(timestamps[-1])

    return new_timestamps, new_positions


def place_photo(photo_string, timestamp_list, location_list):
    def get_photo_location(photo):
        with Image.open(photo) as im:
            exif = im.getexif()
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            if not gps_ifd: return None

            dt = datetime.strptime(exif[ExifTags.Base.DateTime], '%Y:%m:%d %H:%M:%S').replace(tzinfo=loading.tzinfo)
            lon = gps_ifd[ExifTags.GPS.GPSLongitude]
            lat = gps_ifd[ExifTags.GPS.GPSLatitude]
            return dt, sum([x / (60 ** i) for i, x in enumerate(lon)]), sum([x / (60 ** i) for i, x in enumerate(lat)])

    photo_location_index = defaultdict(list)

    if photo_string is None: return photo_location_index

    for photo in photo_string.split(','):
        xxxx = get_photo_location(photo)
        if xxxx is None : continue

        p_dt, p_lon, p_lat = xxxx
        if p_dt+timedelta(hours=1) < timestamp_list[0] or p_dt-timedelta(hours=1) > timestamp_list[-1]: continue

        for i, t in enumerate(timestamp_list):
            if t >= p_dt: break

        if geodesic((p_lat, p_lon), reversed(location_list[i])).km > 1.0: continue

        photo_location_index[i].append(photo)

        # dist_list = [(p_lon - x) ** 2 + (p_lat - y) ** 2 for t, (x, y) in zip(timestamp_list, location_list) if p_dt > t]
        # if dist_list:
        #     idx = dist_list.index(min(dist_list))
        # else:
        #     idx = 0
        # photo_location_index[idx].append(photo)

        # min_i, min_v = -1, 0
        # for i, (t, (x, y)) in enumerate(zip(timestamp_list, location_list)):
        #     v = (p_lon - x) ** 2 + (p_lat - y) ** 2
        #     # print(i, min_i, v, min_v)

        #     if min_i == -1: min_i, min_v = i, v
        #     if t >= p_dt: break
        #     if v < min_v: min_i, min_v = i, v
        # photo_location_index[min_i].append(photo)


    return photo_location_index


def draw_camera_icon(mm, map_image, location_list, photo_location_index, icon='./icon/c3.png'):
    bg = Image.new('RGBA', map_image.size)
    with Image.open(icon) as im:
        for i in photo_location_index.keys():
            x, y = mm.rev_geocode(location_list[i])
            bg.paste(im, (int(x-im.size[0]/2), int(y-im.size[1]/2)))

    map_image.alpha_composite(bg)


def view_window(window_size, map_size, current_p):

    def f(window_p, map_p, p):
        start = max(0, min(map_p - window_p, p - (window_p / 2)))
        end = start + window_p
        return start, end

    assert window_size[0] <= map_size[0] and window_size[1] <= map_size[1], 'window_size > map_size'

    lr = f(window_size[0], map_size[0], current_p[0])
    tb = f(window_size[1], map_size[1], current_p[1])

    return (lr[0], tb[0]), (lr[1], tb[1])


def init_map_object(positions, video_size, zoom, provider):
    x, y = zip(*positions)
    extent = min(x), min(y), max(x), max(y)

    ## FIXME: XXXX
    if (extent[2] - extent[0]) > (extent[3] - extent[1]):
        # landscape
        video_size = (max(video_size), min(video_size))
    else:
        video_size = (min(video_size), max(video_size))

    mm = geotiler.Map(extent=extent, zoom=zoom, provider=provider)
    mm = geotiler.Map(size=(mm.size[0]+video_size[0], mm.size[1]+video_size[1]), extent=extent, provider=provider)
    if mm.zoom > 18: # FIXME: max zoom in API missing
        mm = geotiler.Map(extent=extent, zoom=18)

    print('map size:', mm.size, ', map zoom:', mm.zoom)

    return mm, extent, video_size


def rotate_image(image, current_p, i):
    return image

    image_rotated = image.rotate((i*2/args.fps) % 360, center=current_p)

    return image_rotated


def show_full_route(writer, mm, map_image, extent, window_size, current_p, time_in_sec=2):
    num_frame = int(args.fps * time_in_sec)

    p1, p2 = mm.rev_geocode((extent[0], extent[1])), mm.rev_geocode((extent[2], extent[3]))

    ext1 = (min(p1[0], p2[0]), min(p1[1], p2[1]))
    ext2 = (max(p1[0], p2[0]), max(p1[1], p2[1]))
    mid = ((ext2[0]+ext1[0])/2, (ext2[1]+ext1[1])/2)

    max_r = min(map_image.size[0] / window_size[0], map_image.size[1] / window_size[1])
    r = max((ext2[0] - ext1[0]) / window_size[0], (ext2[1] - ext1[1]) / window_size[1])
    r = max_r # min(r, max_r)
    r_per_frame = (r - 1) / num_frame

    x_per_frame = (mid[0]-current_p[0]) / num_frame
    y_per_frame = (mid[1]-current_p[1]) / num_frame

    for i in range(1, num_frame+1):
        box_width = args.size[0] * (1 + r_per_frame * i)
        box_height = args.size[1] * (1 + r_per_frame * i)

        new_current_p = (current_p[0] + x_per_frame * i, current_p[1] + y_per_frame * i)

        p1, p2 = view_window((box_width, box_height), map_image.size, new_current_p)
        print(i, new_current_p, p1, p2)

        image_resized = map_image.resize(window_size, box=(p1[0], p1[1], p2[0], p2[1]))

        writer.write(image_resized.tobytes())


def render_photo(writer, window_size, photo_list, time_in_sec=1.5):
    print('render photo:', photo_list)

    num_frame = int(args.fps * time_in_sec)

    for photo in photo_list:
        with Image.open(photo) as im:
            im = im.convert('RGBA')

            r = min(window_size[0]/im.size[0], window_size[1]/im.size[1])
            im = im.resize((int(im.size[0] * r), int(im.size[1] * r)))

            bg = Image.new('RGBA', window_size)
            bg.paste(im, ((bg.size[0]-im.size[0])//2, (bg.size[1]-im.size[1])//2))

            for i in range(num_frame): writer.write(bg.tobytes())



#
# parse arguments
#
desc = """
Read positions from set of GPX files and draw them on a map.

The map size is set to 540*960 and can be changed with commandline
parameter.
"""

parser = argparse.ArgumentParser(description=desc)
parser.add_argument(
    '-v', '--verbose', dest='verbose', help='Make a bunch of noise',
    action='store_true'
)
providers = geotiler.providers()
parser.add_argument(
    '-p', '--provider', dest='provider', choices=providers, default='osm',
    help='map provider id'
)
parser.add_argument(
    '-s', '--size', dest='size', nargs=2, type=int, default=(540, 960),
    help='size of map image'
)
parser.add_argument(
    '-z', '--zoom', dest='zoom', type=int, default=14,
    help='zoom of map'
)
parser.add_argument(
    '-f', '--fps', dest='fps', type=int, default=60,
    help='fps of video'
)
parser.add_argument(
    '-d', '--duration', dest='duration', type=int, default=30,
    help='duration of video'
)
parser.add_argument(
    '--photo', dest='photo',
    help='photo to show, sep by comma'
)
parser.add_argument('filename', nargs='+', help='GPX file')
parser.add_argument('output', help='Output video file')

args = parser.parse_args()


#
# read positions and determine map extents
#
print('load gps data...')
timestamps, positions = load_gps_point(args.filename, args.fps * args.duration)
print('gps num:', len(positions))

#
# render map image
#

mm, extent, args.size = init_map_object(positions, args.size, args.zoom, args.provider)

photo_location_index = place_photo(args.photo, timestamps, positions)
print(photo_location_index)


# sys.exit(0)


print('render_map...')
map_image = geotiler.render_map(mm)

draw = ImageDraw.Draw(map_image)

draw_camera_icon(mm, map_image, positions, photo_location_index)

#
# render positions
#

print('render video...')

cmd_string = [
    'ffmpeg',
    '-y', '-hide_banner', '-loglevel', 'info',
    '-f', 'rawvideo',
    '-framerate', str(args.fps),
    '-s', f'{args.size[0]}x{args.size[1]}',
    '-pix_fmt', 'rgba',
    '-i', '-',
    '-vcodec', 'libx264', '-preset', 'veryfast',
    '-r', str(args.fps),
    args.output
]
p = subprocess.Popen(cmd_string, stdin=subprocess.PIPE)

for i in range(len(positions)):
    if i == 0:
        plots = [mm.rev_geocode(positions[i]), mm.rev_geocode(positions[i])]
    else:
        plots = [mm.rev_geocode(positions[i-1]), mm.rev_geocode(positions[i])]

    line_width = 5
    draw.line(plots, fill=(255, 0, 0), width=line_width)

    map_image_copy = map_image.copy()
    new_draw = ImageDraw.Draw(map_image_copy)
    x, y = plots[1]
    new_draw.ellipse((x-line_width, y-line_width, x+line_width, y+line_width), fill=(255, 255, 255))

    image_rotated = rotate_image(map_image_copy, plots[1], i)

    p1, p2 = view_window(args.size, map_image.size, plots[1])
    image_view = image_rotated.crop((p1[0], p1[1], p2[0], p2[1]))

    p.stdin.write(image_view.tobytes())

    if i in photo_location_index: render_photo(p.stdin, args.size, photo_location_index[i])

show_full_route(p.stdin, mm, map_image, extent, args.size, plots[1])

p.stdin.close()
p.wait()

map_image.save(args.output+'.png')
