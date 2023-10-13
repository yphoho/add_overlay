#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

import shutil
import pathlib
import argparse
import functools

import subprocess

import geotiler

from PIL import Image, ImageDraw, ImageFont

import util
import loading


class WriteCounter(object):
    def __init__(self, writer, frame_num=0):
        self.writer = writer
        self.frame_num = 0

    def write(self, something):
        self.frame_num += 1
        self.writer.write(something)

    def current_frame_num(self):
        return self.frame_num


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


def load_gps_point(filename, fps):
    timestamps, positions, sess = loading.load_gps_data(filename)

    num_p = int(len(positions) / (240 / fps))

    r = 1.0 * len(positions) / num_p
    new_positions = [positions[int(r*i)] for i in range(num_p)]
    new_positions.append(positions[-1])
    new_timestamps = [timestamps[int(r*i)] for i in range(num_p)]
    new_timestamps.append(timestamps[-1])

    print('origin gps num:%d, used gps num:%d' % (len(positions), len(new_positions)))

    return new_timestamps, new_positions, sess


def view_window(window_size, map_size, current_p):

    def f(window_p, map_p, p):
        start = max(0, min(map_p - window_p, p - (window_p / 2)))
        end = start + window_p
        return start, end

    assert window_size[0] <= map_size[0] and window_size[1] <= map_size[1], 'window_size > map_size'

    lr = f(window_size[0], map_size[0], current_p[0])
    tb = f(window_size[1], map_size[1], current_p[1])

    return (lr[0], tb[0]), (lr[1], tb[1])


def init_map_object(positions, auto_orientation, video_size, zoom, provider):
    x, y = zip(*positions)
    extent = min(x), min(y), max(x), max(y)

    if auto_orientation:
        if (extent[2] - extent[0]) > (extent[3] - extent[1]):
            # landscape
            video_size = (max(video_size), min(video_size))
        else:
            # portrait
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


def draw_gauge(im, sess):
    if sess is None: return im

    hour = int(sess.total_moving_time)
    minute = int((sess.total_moving_time - hour) * 60)
    text = 'distance: %.1f km, time: %dh%dm, speed: %.1f km/h' %  (sess.total_distance, hour, minute, sess.avg_speed)

    font = ImageFont.truetype('./font/Gidole-Regular.ttf', size=30)
    l = font.getlength(text)

    draw = ImageDraw.Draw(im)
    if l > im.width:
        text = text.replace(', ', '\n')

        x = im.width // 4
        y = im.height // 5

        draw.multiline_text((x, y), text, fill=(0, 0, 255), font=font)
    else:
        x = (im.width - l) // 2
        y = im.height // 10

        draw.text((x, y), text, fill=(0, 0, 255), font=font)

    return im


def show_full_route(writer, mm, map_image, extent, window_size, current_p, sess, time_in_sec=3):
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
        # print(i, new_current_p, p1, p2)

        image_view = map_image.resize(window_size, box=(p1[0], p1[1], p2[0], p2[1]))
        image_view = draw_gauge(image_view, sess)

        writer.write(image_view.tobytes())


def smooth_center(rev_geocode, location_list, i, window2=7):
    start, end = max(0, i-window2), min(len(location_list), i+window2)
    p_list = [rev_geocode(l) for l in location_list[start:end]]

    x = sum([a for a, _ in p_list]) / len(p_list)
    y = sum([a for _, a in p_list]) / len(p_list)

    # print(rev_geocode(location_list[i]), (x, y))

    return (x, y)


def scale_video_clip(video_list, window_size, fps, keep_audio):
    clip_scale_proc_dict = {}
    for video in video_list:
        outfile = video + '.' + str(keep_audio) + '.scale.mp4'

        if not os.path.exists(outfile):
            print('scale video:', video)
            cmd_string = util.splice_scale_cmd_string(video, outfile, window_size, fps, keep_audio)
        else:
            cmd_string = ['true']

        ## NOTE: MUST open it with stdin when run parallel, https://stackoverflow.com/a/6659191/1079820
        p = subprocess.Popen(cmd_string, stdin=subprocess.PIPE)
        # p.stdin.close(); p.wait()

        clip_scale_proc_dict[video] = [p, outfile]

    return clip_scale_proc_dict


def wait_proc_and_add_silent_audio(clip_starttime_list, clip_scale_proc_dict, keep_audio):
    new_clip_starttime_list = []
    for clip, starttime in clip_starttime_list:
        p, clip = clip_scale_proc_dict[clip]
        p.stdin.close(); p.wait()

        new_clip_starttime_list.append((clip, starttime))

        if keep_audio and not util.exists_audio(clip): ffmpeg_add_silent_audio(clip)

    return new_clip_starttime_list


def ffmpeg_concat_main_and_clip(main_video, clip_starttime_list, keep_audio, is_release):
    if not clip_starttime_list: return

    print('concat video...')

    clip_list, filter_complex = [], []
    inpoint = 0.0
    for i, (clip, outpoint) in enumerate(clip_starttime_list):
        clip_list.append(clip)

        filter_complex.append('[0:v]trim=%.3f:%.3f,setpts=PTS-STARTPTS[v%d];' % (inpoint, outpoint, i))
        if keep_audio: filter_complex.append('[0:a]atrim=%.3f:%.3f,asetpts=PTS-STARTPTS[a%d];' % (inpoint, outpoint, i))

        inpoint = outpoint

    filter_complex.append('[0:v]trim=start=%.3f,setpts=PTS-STARTPTS[v%d];' % (inpoint, i+1))
    if keep_audio: filter_complex.append('[0:a]atrim=start=%.3f,asetpts=PTS-STARTPTS[a%d];' % (inpoint, i+1))

    filter_complex.append('[v0]')
    if keep_audio: filter_complex.append('[a0]')
    for i in range(1, len(clip_list)+1):
        if keep_audio: filter_complex.append('[%d:v][%d:a][v%d][a%d]' % (i, i, i, i))
        else: filter_complex.append('[%d:v][v%d]' % (i, i))

    video_map, audio_map = '[outv]', '[outa]'
    if keep_audio:
        filter_complex.append('concat=n=%d:v=1:a=1%s%s' % (len(clip_list)*2+1, video_map, audio_map))
    else:
        audio_map = None
        filter_complex.append('concat=n=%d:v=1:a=0%s' % (len(clip_list)*2+1, video_map))

    # print(filter_complex)

    outfile = main_video + '.concat.mp4'
    cmd_string = util.splice_concat_cmd_string2([main_video] + clip_list, outfile, ''.join(filter_complex), video_map, audio_map, is_release)
    subprocess.run(cmd_string)

    os.rename(outfile, main_video)


    # concat_file = os.path.basename(main_video) + '.concat.txt'
    # f = open(concat_file, 'w')

    # inpoint = 0.0
    # for clip, outpoint in clip_starttime_list:
    #     f.write('file \'%s\'\ninpoint %.3f\noutpoint %.3f\n' % (main_video, inpoint, outpoint))
    #     f.write('file \'%s\'\n' % clip)

    #     inpoint = outpoint
    # f.write('file \'%s\'\ninpoint %.3f\n' % (main_video, inpoint))
    # f.close()

    # outfile = main_video + '.concat.mp4'
    # cmd_string = util.splice_concat_cmd_string(concat_file, outfile, is_release)
    # subprocess.run(cmd_string)

    # os.rename(outfile, main_video)


def ffmpeg_add_audio(video_file, audio_file):
    outfile = video_file + '.audio.mp4'

    cmd_string = util.splice_audio_cmd_string(outfile, video_file, audio_file)
    subprocess.run(cmd_string)

    os.rename(outfile, video_file)


ffmpeg_add_silent_audio = functools.partial(ffmpeg_add_audio, audio_file=None)


#
# parse arguments
#
desc = """
Read positions from set of GPX files and draw them on a map.
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
parser.add_argument(
    '--release', dest='is_release', action='store_true',
    help='set it when the video is to publish'
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
    '--auto-orientation', dest='auto_orientation', action='store_true',
    help='swap the size by the shape of route automatically'
)
parser.add_argument(
    '-z', '--zoom', dest='zoom', type=int, default=14,
    help='zoom of map'
)
parser.add_argument(
    '-f', '--fps', dest='fps', type=int, default=30,
    help='fps of video'
)
parser.add_argument(
    '--audio', dest='audio', default = None,
    help='the audio to play'
)
parser.add_argument(
    '--photo', dest='photo', default = None,
    help='a file with photo name and [or] datetime as line'
)
parser.add_argument(
    '--keep-audio', dest='keep_audio', action='store_true',
    help='keep the clip audio or not'
)
parser.add_argument('filename', nargs='+', help='GPX file')
parser.add_argument('output', help='Output video file')

args = parser.parse_args()

args.cache_dir.mkdir(parents=True, exist_ok=True)

#
# read positions and determine map extents
#
print('load gps data...')
timestamps, positions, sess = load_gps_point(args.filename, args.fps)

#
# render map image
#

mm, extent, args.size = init_map_object(positions, args.auto_orientation, args.size, args.zoom, args.provider)

is_mars_in_china = mm.provider.name.endswith('.mars_in_china')

if is_mars_in_china: positions = util.fix_mars_in_china(positions)

photo_render = util.PhotoRender(args.photo, timestamps, positions, is_mars_in_china, args.is_release)
photo_render.debug()

clip_scale_proc_dict = scale_video_clip(photo_render.videos(), args.size, args.fps, args.keep_audio)


# sys.exit(1)


print('render_map...')
map_image = my_render_map()(mm)

draw = ImageDraw.Draw(map_image)

photo_render.draw_camera_icon(mm, map_image)

#
# render positions
#

print('render route...')

cmd_string = util.splice_main_cmd_string(args.output, args.size, args.fps, args.is_release)

p = subprocess.Popen(cmd_string, stdin=subprocess.PIPE)
write_counter = WriteCounter(p.stdin)

clip_starttime_list = []
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

    write_counter.write(image_view.tobytes())

    photo_info_list = photo_render.render_photo_if_need(p.stdin, write_counter, args.size, dt, args.fps)

    clip_starttime_list.extend([(pi.photo_name, write_counter.current_frame_num()/args.fps) for pi in photo_info_list if pi.is_video])

show_full_route(write_counter, mm, map_image, extent, args.size, plots[1], sess)

print('frame num:', write_counter.current_frame_num())

# p.stdin.flush()
p.stdin.close(); p.wait()

map_image.save(args.output+'.png')

shutil.copy2(args.output, args.output+'.route.mp4')

if args.keep_audio: ffmpeg_add_audio(args.output, args.audio)

new_clip_starttime_list = wait_proc_and_add_silent_audio(clip_starttime_list, clip_scale_proc_dict, args.keep_audio)

ffmpeg_concat_main_and_clip(args.output, new_clip_starttime_list, args.keep_audio, args.is_release)
if not args.keep_audio and args.audio: ffmpeg_add_audio(args.output, args.audio)
