#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

import math

import shutil
import pathlib
import argparse
import functools

import subprocess

from geopy.distance import geodesic

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


def my_render_map(cache_dir=pathlib.Path('./'), cache_file='tilecache.sqlite', is_cache=True):
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

    db = SqliteDict(filename=str(cache_dir.joinpath(cache_file)), autocommit=True)
    downloader = sqlite_downloader(db)
    return functools.partial(geotiler.render_map, downloader=downloader)


def load_gps_point(filename, fps, is_mars_in_china):
    timestamps, positions, sess = loading.load_gps_data(filename)

    num_p = int(len(positions) / (240 / fps))

    r = 1.0 * len(positions) / num_p
    new_positions = [positions[int(r*i)] for i in range(num_p)]
    new_positions.append(positions[-1])
    new_timestamps = [timestamps[int(r*i)] for i in range(num_p)]
    new_timestamps.append(timestamps[-1])

    print('origin gps num:%d, used gps num:%d' % (len(positions), len(new_positions)))

    if is_mars_in_china: new_positions = util.fix_mars_in_china(new_positions)

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

    if zoom == 0:
        distance = geodesic((extent[1], extent[0]), (extent[3], extent[2])).km
        print('max distance: ', distance)

        zoom = 14 if distance > 7.0 else 15

    if auto_orientation:
        if (extent[2] - extent[0]) > (extent[3] - extent[1]):
            # landscape
            video_size = (max(video_size), min(video_size))
        else:
            # portrait
            video_size = (min(video_size), max(video_size))

    mm = geotiler.Map(extent=extent, zoom=zoom, provider=provider)

    # mm = geotiler.Map(size=(mm.size[0]+video_size[0], mm.size[1]+video_size[1]), extent=extent, provider=provider)
    mm.size = max(video_size[0], mm.size[0]+video_size[0]//2), max(video_size[1], mm.size[1]+video_size[1]//2)

    print('map size:', mm.size, ', map zoom:', mm.zoom, ', map extent:', mm.extent)

    return mm, extent, video_size


def rotate_image(image, current_p, i, fps):
    return image

    image_rotated = image.rotate((i*2/fps) % 360, center=current_p)

    return image_rotated


def find_best_font(text, window_size, align='center', font_file='./font/Gidole-Regular.ttf'):
    align_list = ('center', '1/3')

    if align not in align_list: align = align_list[0]

    text = max([(len(x), x) for x in text.split('\n')])[1]

    if align == '1/3':
        size = int(window_size[0] * 2 / len(text) * 0.67)
    else:
        size = int(window_size[0] * 2 / len(text) * 0.9)
    print('font size:', size)

    font = ImageFont.truetype(font_file, size=size)

    return font


def draw_gauge(im, sess):
    if sess.total_distance == 0: return im

    hour = int(sess.total_moving_time)
    minute = math.ceil((sess.total_moving_time - hour) * 60)
    time_text = '%dh%dm' % (hour, minute) if hour != 0 else '%dm' % minute
    text = 'distance: %.1f km, elevation: %d m\ntime: %s, speed: %.1f km/h' %  (sess.total_distance, sess.total_ascent, time_text, sess.avg_speed)
    if im.width < im.height: text = text.replace(', ', '\n')

    if not hasattr(draw_gauge, 'font'):
        draw_gauge.font = find_best_font(text, im.size)
    text_spacing = draw_gauge.font.size // 3

    draw = ImageDraw.Draw(im)
    box = draw.textbbox((0, 0), text, draw_gauge.font, spacing=text_spacing)

    x = (im.width // 2) - ((box[2] - box[0]) // 2)
    y = (im.height // 3) - ((box[3] - box[1]) // 2)

    draw.text((x, y), text, fill=(0, 0, 255), font=draw_gauge.font, spacing=text_spacing)

    return im


def show_starter(write_counter, im, sess, fps, time_in_sec=3):
    text_date = sess.start_time.strftime('%B %d, %Y')

    text_begin_time = sess.start_time.strftime('%H:%M:%S')
    text_end_time = sess.dt.strftime('%H:%M:%S')
    text_time = '%s -- %s' % (text_begin_time, text_end_time)

    full_text = text_date + '\n' + text_time

    print(text_date, text_time)

    im = im.copy()
    draw = ImageDraw.Draw(im)

    font = find_best_font(full_text, im.size, '1/3')
    text_spacing = font.size // 3

    box = draw.textbbox((0, 0), full_text, font, spacing=text_spacing)

    x = (im.width // 3) - ((box[2] - box[0]) // 2)
    y = (im.height // 3) - ((box[3] - box[1]) // 2)

    for i in range(fps * time_in_sec):
        if i == int(fps * 0.3):
            draw.text((x, y), text_date, fill=(0, 0, 255), font=font, spacing=text_spacing)
        elif i == int(fps * 1.0):
            draw.text((x, y), full_text, fill=(0, 0, 255), font=font, spacing=text_spacing)

        write_counter.write(im.tobytes())


def show_full_route(writer, mm, map_image, extent, window_size, fps, current_p, sess, time_in_sec=3):
    num_frame = int(fps * time_in_sec)

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
        box_width = window_size[0] * (1 + r_per_frame * i)
        box_height = window_size[1] * (1 + r_per_frame * i)

        new_current_p = (current_p[0] + x_per_frame * i, current_p[1] + y_per_frame * i)

        p1, p2 = view_window((box_width, box_height), map_image.size, new_current_p)
        # print(i, new_current_p, p1, p2)

        image_view = map_image.resize(window_size, box=(p1[0], p1[1], p2[0], p2[1]))
        image_view = draw_gauge(image_view, sess)

        writer.write(image_view.tobytes())

    for i in range(2 * fps): writer.write(image_view.tobytes())


def smooth_center(rev_geocode, location_list, i, window2=7):
    start, end = max(0, i-window2), min(len(location_list), i+window2)
    p_list = [rev_geocode(l) for l in location_list[start:end]]

    x = sum([a for a, _ in p_list]) / len(p_list)
    y = sum([a for _, a in p_list]) / len(p_list)

    # print(rev_geocode(location_list[i]), (x, y))

    return (x, y)


def render_route(output, window_size, fps, extent, mm, map_image, positions, timestamps, sess, is_release):
    cmd_string = util.splice_main_cmd_string(output, window_size, fps, is_release)

    p = subprocess.Popen(cmd_string, stdin=subprocess.PIPE)
    write_counter = WriteCounter(p.stdin)

    draw = ImageDraw.Draw(map_image)

    line_width = 5
    clip_starttime_list = []
    for i, dt in enumerate(timestamps):
        if i == 0:
            plots = [mm.rev_geocode(positions[i]), mm.rev_geocode(positions[i])]
        else:
            plots = [mm.rev_geocode(positions[i-1]), mm.rev_geocode(positions[i])]
            draw.line(plots, fill=(255, 0, 0), width=line_width)

        # center_point = plots[1]
        center_point = smooth_center(mm.rev_geocode, positions, i)
        p1, p2 = view_window(window_size, map_image.size, center_point)
        image_view = map_image.crop((p1[0], p1[1], p2[0], p2[1]))

        if i == 0: show_starter(write_counter, image_view, sess, fps)

        new_plot_1 = (plots[1][0] - p1[0], plots[1][1] - p1[1])

        new_draw = ImageDraw.Draw(image_view)
        x, y = new_plot_1
        new_draw.ellipse((x-line_width, y-line_width, x+line_width, y+line_width), fill=(255, 255, 255))

        # image_view = rotate_image(image_view, new_plot_1, i, fps)

        write_counter.write(image_view.tobytes())

        photo_info_list = photo_render.render_photo_if_need(p.stdin, write_counter, window_size, dt, fps)

        clip_starttime_list.extend([(pi.photo_name, write_counter.current_frame_num()/fps) for pi in photo_info_list if pi.is_video])

    show_full_route(write_counter, mm, map_image, extent, window_size, fps, plots[1], sess)

    print('frame num:', write_counter.current_frame_num())

    # p.stdin.flush()
    p.stdin.close(); p.wait()

    map_image.save(output+'.png')
    shutil.copy2(output, output+'.route.mp4')

    return clip_starttime_list


def scale_video_clip(video_list, window_size, fps):
    clip_scale_proc_dict = {}
    for video in video_list:
        outfile = video + '.' + str(window_size) + '.scale.mp4'

        if not os.path.exists(outfile):
            print('scale clip:', video)
            cmd_string = util.splice_scale_cmd_string(video, outfile, window_size, fps)
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

        if keep_audio and not util.exists_audio(clip):
            new_clip = clip + '.silent.mp4'
            if not os.path.exists(new_clip): ffmpeg_add_silent_audio(clip, outfile=new_clip)
            clip = new_clip

        new_clip_starttime_list.append((clip, starttime))

    return new_clip_starttime_list


def ffmpeg_concat_main_and_clip(main_video, clip_starttime_list, keep_audio, is_release):
    if not clip_starttime_list: return

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


def ffmpeg_add_audio(video_file, audio_file, outfile=None):
    if outfile is None:
        outfile = video_file + '.audio.mp4'
        rename = True
    else:
        rename = False

    cmd_string = util.splice_audio_cmd_string(outfile, video_file, audio_file)
    subprocess.run(cmd_string)

    if rename: os.rename(outfile, video_file)


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
    '-z', '--zoom', dest='zoom', type=int, default=0,
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

provider = geotiler.provider.find_provider(args.provider)
is_mars_in_china = provider.name.endswith('.mars_in_china')

print('load gps data...')
timestamps, positions, sess = load_gps_point(args.filename, args.fps, is_mars_in_china)

photo_render = util.PhotoRender(args.photo, timestamps, positions, is_mars_in_china, args.is_release)
photo_render.debug()

clip_scale_proc_dict = scale_video_clip(photo_render.videos(), args.size, args.fps)


# sys.exit(1)


print('render_map...')
mm, extent, args.size = init_map_object(positions, args.auto_orientation, args.size, args.zoom, provider)
map_image = my_render_map(args.cache_dir)(mm)

photo_render.draw_camera_icon(mm, map_image)

print('render route...')
clip_starttime_list = render_route(args.output, args.size, args.fps, extent, mm, map_image, positions, timestamps, sess, args.is_release)

if args.keep_audio: ffmpeg_add_audio(args.output, args.audio)

print('wait scale...')
new_clip_starttime_list = wait_proc_and_add_silent_audio(clip_starttime_list, clip_scale_proc_dict, args.keep_audio)

print('concat clips...')
ffmpeg_concat_main_and_clip(args.output, new_clip_starttime_list, args.keep_audio, args.is_release)
if not args.keep_audio and args.audio: ffmpeg_add_audio(args.output, args.audio)
