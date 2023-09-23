#!/usr/bin/python3

import sys

import pathlib
import argparse
import functools

import subprocess

import geotiler

from PIL import Image, ImageDraw

import loading
from util import PhotoRender, fix_mars_in_china


def my_render_map(is_cache=True):
    if not is_cache:
        return geotiler.render_map

    from sqlitedict import SqliteDict

    def sqlite_downloader(db: SqliteDict, timeout=3600*24*30):
        from geotiler.cache import caching_downloader
        from geotiler.tile.io import fetch_tiles

        def get_key(key):
            return db.get(key, None)

        def set_key(key, value):
            if value:
                db.setdefault(key, value)

        return functools.partial(caching_downloader, get_key, set_key, fetch_tiles)

    db = SqliteDict(filename=str(args.cache_dir.joinpath("tilecache.sqlite")), autocommit=True)
    downloader = sqlite_downloader(db)
    return functools.partial(geotiler.render_map, downloader=downloader)


def load_gps_point(filename, num_p):
    timestamps, positions = loading.load_gps_data(filename)

    # print(timestamps[0].timestamp(), type(timestamps[0]))
    print('origin gps num:', len(positions))

    # positions = positions[int(len(positions)/2):]

    num_p = max(num_p, len(positions) // 4)

    r = 1.0 * len(positions) / num_p
    new_positions = [positions[int(r*i)] for i in range(num_p)]
    new_positions.append(positions[-1])
    new_timestamps = [timestamps[int(r*i)] for i in range(num_p)]
    new_timestamps.append(timestamps[-1])

    return new_timestamps, new_positions


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

    print('map size:', mm.size, ', map zoom:', mm.zoom, ', map extent:', mm.extent)

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


def smooth_center(rev_geocode, location_list, i, window2=7):
    start, end = max(0, i-window2), min(len(location_list), i+window2)
    p_list = [rev_geocode(l) for l in location_list[start:end]]

    x = sum([a for a, _ in p_list]) / len(p_list)
    y = sum([a for _, a in p_list]) / len(p_list)

    # print(rev_geocode(location_list[i]), (x, y))

    return (x, y)


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
parser.add_argument(
    '--cache-dir', dest='cache_dir', type=pathlib.Path, default=pathlib.Path.home() / '.cache/geotiler/',
    help='location of cache(map tile, ...)'
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
    '--photo', dest='photo', default = None,
    help='a file with photo name and [or] datetime as line'
)
parser.add_argument('filename', nargs='+', help='GPX file')
parser.add_argument('output', help='Output video file')

args = parser.parse_args()

print('cache_dir:', args.cache_dir)
args.cache_dir.mkdir(parents=True, exist_ok=True)

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

is_mars_in_china = mm.provider.name.endswith('.mars_in_china')

if is_mars_in_china: positions = fix_mars_in_china(positions)

photo_render = PhotoRender(args.photo, timestamps, positions, is_mars_in_china)
photo_render.debug()


# sys.exit(0)


render_map = my_render_map()

print('render_map...')
map_image = render_map(mm)

draw = ImageDraw.Draw(map_image)

photo_render.draw_camera_icon(mm, map_image)

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

for i, dt in enumerate(timestamps):
    if i == 0:
        plots = [mm.rev_geocode(positions[i]), mm.rev_geocode(positions[i])]
    else:
        plots = [mm.rev_geocode(positions[i-1]), mm.rev_geocode(positions[i])]

    line_width = 5
    draw.line(plots, fill=(255, 0, 0), width=line_width)

    # center_point = plots[1]
    center_point = smooth_center(mm.rev_geocode, positions, i)
    p1, p2 = view_window(args.size, map_image.size, center_point)
    image_view = map_image.crop((p1[0], p1[1], p2[0], p2[1]))

    new_plot_1 = (plots[1][0] - p1[0], plots[1][1] - p1[1])

    new_draw = ImageDraw.Draw(image_view)
    x, y = new_plot_1
    new_draw.ellipse((x-line_width, y-line_width, x+line_width, y+line_width), fill=(255, 255, 255))

    # image_view = rotate_image(image_view, new_plot_1, i)

    p.stdin.write(image_view.tobytes())

    photo_render.render_photo_if_need(p.stdin, args.size, dt, args.fps)

show_full_route(p.stdin, mm, map_image, extent, args.size, plots[1])

p.stdin.close()
p.wait()

map_image.save(args.output+'.png')
