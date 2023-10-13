#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

from collections import defaultdict, namedtuple
from datetime import datetime, timedelta

from pathlib import Path

import subprocess

from geopy.distance import geodesic

import exif
from PIL import Image


def wgs2gcj(lon, lat):
    import eviltransform
    lat, lon = eviltransform.wgs2gcj(lat, lon)
    return lon, lat


def fix_mars_in_china(location):
    # # gps not in china
    # l = location[0] if isinstance(location, list) else location
    # if not is_in_china(l): return location

    # print('let us fix mars-in-china')

    if isinstance(location, list):
        return [wgs2gcj(*x) for x in location]
    else:
        return wgs2gcj(*location)


def check_file_type(filepath):
        suffix = Path(filepath).suffix.lower()
        if suffix in ['.jpg', '.jpeg', '.png']:
            return 'image'
        elif suffix in ['.mp4', '.mov']:
            return 'video'
        else:
            return None


def splice_main_cmd_string(outfile, window_size, fps, is_release):
    width, height = window_size
    cmd_string = [
        'ffmpeg',
        '-y', '-hide_banner', '-loglevel', 'info',
        '-f', 'rawvideo', '-framerate', str(fps), '-s', f'{width}x{height}', '-pix_fmt', 'rgba',
        '-i', '-',
        '-r', str(fps),
        '-vcodec', 'libx264'
    ]

    if is_release: cmd_string.extend(['-preset', 'fast'])
    else: cmd_string.extend(['-preset', 'superfast'])

    cmd_string.append(outfile)
    print(cmd_string)

    return cmd_string


def splice_clip_cmd_string(infile, window_size, fps, is_release):
    width, height = window_size
    cmd_string = [
        'ffmpeg',
        '-y', '-hide_banner', '-loglevel', 'error',
        '-i', infile,
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:-1:-1:color=black',
        '-f', 'rawvideo', '-r', str(fps), '-s', f'{width}x{height}', '-pix_fmt', 'rgba'
    ]

    if is_release: cmd_string.extend(['-preset', 'fast'])
    else: cmd_string.extend(['-preset', 'ultrafast'])

    cmd_string.append('-')
    print(cmd_string)

    return cmd_string


def splice_scale_cmd_string(infile, outfile, window_size, fps, keep_audio):
    width, height = window_size
    cmd_string = [
        'ffmpeg',
        '-y', '-hide_banner', '-loglevel', 'error',
        '-i', infile,
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:-1:-1:color=black',
        '-r', str(fps),
        '-c:v', 'libx264'
    ]

    if keep_audio: cmd_string.extend(['-c:a', 'aac'])
    else: cmd_string.append('-an')

    cmd_string.extend(['-preset', 'fast'])

    cmd_string.append(outfile)
    print(cmd_string)

    return cmd_string


def splice_concat_cmd_string(concat_file, outfile, is_release):
    cmd_string = [
        'ffmpeg',
        '-y', '-hide_banner', '-loglevel', 'info',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file,
        '-c:v', 'libx264', '-c:a', 'aac'
        # '-c', 'copy'
    ]

    if is_release: cmd_string.extend(['-preset', 'fast'])
    else: cmd_string.extend(['-preset', 'superfast'])

    cmd_string.append(outfile)
    print(cmd_string)

    return cmd_string


def splice_concat_cmd_string2(concat_file_list, outfile, filter_complex, video_map, audio_map, is_release):
    cmd_string = [
        'ffmpeg',
        '-y', '-hide_banner', '-loglevel', 'info'
    ]

    for v in concat_file_list:
        cmd_string.extend(['-i', v])

    cmd_string.extend([
        '-filter_complex', filter_complex,
        '-map', video_map
    ])
    if audio_map is not None:
        cmd_string.extend(['-map', audio_map])

    if is_release: cmd_string.extend(['-preset', 'fast'])
    else: cmd_string.extend(['-preset', 'superfast'])

    cmd_string.append(outfile)
    print(cmd_string)

    return cmd_string


def splice_audio_cmd_string(outfile, video_file, audio_file=None):
    cmd_string = [
        'ffmpeg',
        '-y', '-hide_banner', '-loglevel', 'error',
        '-i', video_file
    ]

    if audio_file:
        cmd_string.extend(['-stream_loop', '-1', '-i', audio_file])
    else:
        cmd_string.extend(['-f', 'lavfi', '-i', 'anullsrc'])

    cmd_string.extend([
        '-c:v', 'copy', '-c:a', 'aac',
        '-map', '0:v:0', '-map', '1:a:0',
        '-shortest',
        outfile
    ])

    print(cmd_string)

    return cmd_string


def exists_audio(video_file):
    r = subprocess.run(['ffprobe', '-hide_banner', '-loglevel', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', video_file], capture_output=True)
    return r.stdout.strip() == b'audio'


PhotoInfo = namedtuple('PhotoInfo', ['photo_name', 'is_video', 'dt', 'lon', 'lat'], defaults=(None, False, None, None, None))

class PhotoRender(object):
    def __init__(self, filename, timestamp_list, location_list, is_mars_in_china=False, is_release=False):
        self.is_mars_in_china = is_mars_in_china
        self.is_release = is_release

        self.photo_info_list = []
        self.photo_location_dict = defaultdict(list)

        self.is_init = filename is not None
        if not self.is_init or not os.path.exists(filename): return

        self._read_photo_file(filename, is_mars_in_china)
        self._find_photo_location(timestamp_list, location_list)

    def render_photo_if_need(self, pipe_out, writer, window_size, dt, fps, time_in_sec=1.5):
        if dt not in self.photo_location_dict: return []

        num_frame = int(fps * time_in_sec)

        for photo_info in self.photo_location_dict[dt]:
            if photo_info.is_video:
                continue

                print('render video:', photo_info.photo_name)

                cmd_string = splice_clip_cmd_string(photo_info.photo_name, window_size, fps, self.is_release)

                p2 = subprocess.Popen(cmd_string, stdout=pipe_out)
                p2.wait()

            else:
                print('render photo:', photo_info.photo_name)

                im = Image.open(photo_info.photo_name).convert('RGBA')

                r = min(window_size[0]/im.size[0], window_size[1]/im.size[1])
                im = im.resize((int(im.size[0] * r), int(im.size[1] * r)))

                bg = Image.new('RGBA', window_size)
                bg.paste(im, ((bg.size[0]-im.size[0])//2, (bg.size[1]-im.size[1])//2))

                for i in range(num_frame): writer.write(bg.tobytes())

        return self.photo_location_dict[dt]

    def videos(self):
        for pi_list in self.photo_location_dict.values():
            for pi in pi_list:
                if pi.is_video:
                    yield pi.photo_name

    def draw_camera_icon(self, mm, map_image, icon='./icon/c3.png', icon_video='./icon/c1.png'):
        bg = Image.new('RGBA', map_image.size)
        im = Image.open(icon)
        im_video = Image.open(icon_video)

        for photo_info_list in self.photo_location_dict.values():
            for photo_info in photo_info_list:
                x, y = mm.rev_geocode((photo_info.lon, photo_info.lat))
                if photo_info.is_video:
                    bg.paste(im_video, (int(x-im_video.size[0]/2), int(y-im_video.size[1]/2)))
                else:
                    bg.paste(im, (int(x-im.size[0]/2), int(y-im.size[1]/2)))

        map_image.alpha_composite(bg)

    def debug(self):
        for x in self.photo_info_list: print(x)
        for x in self.photo_location_dict.items(): print(x)

    def _read_photo_file(self, filename, is_mars_in_china):
        for line in open(filename):
            if line.startswith('#') or line.startswith('\n'): continue

            xxxx = line.strip().split(' ')

            photo_name = xxxx[0]
            if not os.path.exists(photo_name): continue

            file_type = check_file_type(photo_name)
            if file_type is None: continue

            is_video = (file_type == 'video')

            if len(xxxx) > 1:
                dt = datetime.strptime(xxxx[1], '%Y-%m-%dT%H:%M:%S%z')
                self.photo_info_list.append(PhotoInfo(photo_name, is_video, dt))
            elif len(xxxx) == 1 and not is_video:
                aaa = self._read_photo_location_from_file(photo_name)
                if aaa is None : continue

                dt, lon, lat = aaa
                if is_mars_in_china:
                    lon, lat = fix_mars_in_china((lon, lat))

                self.photo_info_list.append(PhotoInfo(photo_name, is_video, dt, lon, lat))
            else:
                print(photo_name + ' has no timestamp, skip')

    def _find_photo_location(self, timestamp_list, location_list):
        for photo_name, is_video, dt, lon, lat in self.photo_info_list:
            if dt+timedelta(hours=1) < timestamp_list[0] or dt-timedelta(hours=1) > timestamp_list[-1]: continue

            for i, t in enumerate(timestamp_list):
                if t >= dt: break

            if lon is not None and geodesic((lat, lon), reversed(location_list[i])).km > 1.0: continue

            photo_info = PhotoInfo(photo_name, is_video, dt, location_list[i][0], location_list[i][1])
            self.photo_location_dict[timestamp_list[i]].append(photo_info)

        for v in self.photo_location_dict.values():
            v.sort(key=lambda a: (a.is_video, a.dt))

    def _read_photo_location_from_file(self, photo):
        with open(photo, 'rb') as image_file:
            my_image = exif.Image(image_file)

        if not 'gps_longitude' in my_image.list_all(): return None

        dt = datetime.strptime(my_image.datetime+my_image.offset_time.replace(':', ''), '%Y:%m:%d %H:%M:%S%z')
        lon = float(sum([x / (60 ** i) for i, x in enumerate(my_image.gps_longitude)]))
        lat = float(sum([x / (60 ** i) for i, x in enumerate(my_image.gps_latitude)]))

        return dt, lon, lat


if __name__ == '__main__':
    import loading
    timestamp_list, location_list = loading.load_gps_data(['./tuanpohu.gpx'])

    photo_render = PhotoRender('p.txt', timestamp_list, location_list)
    photo_render.debug()
