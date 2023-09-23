#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

from collections import defaultdict, namedtuple
from datetime import datetime, timedelta

from geopy.distance import geodesic

from PIL import Image, ExifTags

from loading import tzinfo


def wgs2gcj(lon, lat):
    import eviltransform
    lat, lon = eviltransform.wgs2gcj(lat, lon)
    return lon, lat


def fix_mars_in_china(location):
    # # gps not in china
    # l = location[0] if isinstance(location, list) else location
    # if not is_in_china(l): return location

    print('let us fix mars-in-china')

    if isinstance(location, list):
        return [wgs2gcj(*x) for x in location]
    else:
        return wgs2gcj(*location)


PhotoInfo = namedtuple('PhotoInfo', ['photoname', 'dt', 'lon', 'lat'], defaults=(None, None, None, None))

class PhotoRender(object):
    def __init__(self, filename, timestamp_list, location_list, is_mars_in_china=False):
        self.is_mars_in_china = is_mars_in_china

        self.photo_info_list = []
        self.photo_location_dict = defaultdict(list)

        self.is_init = filename is not None
        if not self.is_init or not os.path.exists(filename): return

        self._read_photo_file(filename, is_mars_in_china)
        self._find_photo_location(timestamp_list, location_list)

    def render_photo_if_need(self, writer, window_size, dt, fps, time_in_sec=1.5):
        if dt not in self.photo_location_dict: return

        num_frame = int(fps * time_in_sec)

        for photo, _, _, _ in self.photo_location_dict[dt]:
            print('render photo:', photo)
            with Image.open(photo) as im:
                im = im.convert('RGBA')

                r = min(window_size[0]/im.size[0], window_size[1]/im.size[1])
                im = im.resize((int(im.size[0] * r), int(im.size[1] * r)))

                bg = Image.new('RGBA', window_size)
                bg.paste(im, ((bg.size[0]-im.size[0])//2, (bg.size[1]-im.size[1])//2))

                for i in range(num_frame): writer.write(bg.tobytes())

    def draw_camera_icon(self, mm, map_image, icon='./icon/c3.png'):
        bg = Image.new('RGBA', map_image.size)
        with Image.open(icon) as im:
            for photo_info_list in self.photo_location_dict.values():
                for photo, _, lon, lat in photo_info_list:
                    x, y = mm.rev_geocode((lon, lat))
                    bg.paste(im, (int(x-im.size[0]/2), int(y-im.size[1]/2)))

        map_image.alpha_composite(bg)

    def debug(self):
        for x in self.photo_info_list: print(x)
        for x in self.photo_location_dict.items(): print(x)

    def _read_photo_file(self, filename, is_mars_in_china):
        for line in open(filename):
            xxxx = line.strip().strip().split(' ')

            photo_name = xxxx[0]
            if not os.path.exists(photo_name): continue

            if len(xxxx) == 1:
                aaa = self._read_photo_location_from_file(photo_name)
                if aaa is None : continue

                dt, lon, lat = aaa
                if is_mars_in_china:
                    lon, lat = fix_mars_in_china((lon, lat))

                self.photo_info_list.append(PhotoInfo(photo_name, dt, lon, lat))
            elif len(xxxx) == 3:
                dt = datetime.strptime(' '.join(xxxx[1:]), '%Y:%m:%d %H:%M:%S').replace(tzinfo=tzinfo)
                self.photo_info_list.append(PhotoInfo(photo_name, dt))
            else:
                print(photo_name + ' has no timestamp, skip')

    def _find_photo_location(self, timestamp_list, location_list):
        for photoname, dt, lon, lat in self.photo_info_list:
            if dt+timedelta(hours=1) < timestamp_list[0] or dt-timedelta(hours=1) > timestamp_list[-1]: continue

            for i, t in enumerate(timestamp_list):
                if t >= dt: break

            if lon is not None and geodesic((lat, lon), reversed(location_list[i])).km > 1.0: continue

            self.photo_location_dict[timestamp_list[i]].append(
                    PhotoInfo(photoname, dt, location_list[i][0], location_list[i][1]))

    def _read_photo_location_from_file(self, photo):
        with Image.open(photo) as im:
            exif = im.getexif()
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            if not gps_ifd: return None

            dt = datetime.strptime(exif[ExifTags.Base.DateTime], '%Y:%m:%d %H:%M:%S').replace(tzinfo=tzinfo)
            lon = float(sum([x / (60 ** i) for i, x in enumerate(gps_ifd[ExifTags.GPS.GPSLongitude])]))
            lat = float(sum([x / (60 ** i) for i, x in enumerate(gps_ifd[ExifTags.GPS.GPSLatitude])]))

            return dt, lon, lat


def place_photo(photo_string, timestamp_list, location_list, is_mars_in_china):
    def get_photo_location(photo):
        with Image.open(photo) as im:
            exif = im.getexif()
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            if not gps_ifd: return None

            dt = datetime.strptime(exif[ExifTags.Base.DateTime], '%Y:%m:%d %H:%M:%S').replace(tzinfo=tzinfo)
            lon = sum([x / (60 ** i) for i, x in enumerate(gps_ifd[ExifTags.GPS.GPSLongitude])])
            lat = sum([x / (60 ** i) for i, x in enumerate(gps_ifd[ExifTags.GPS.GPSLatitude])])

            return dt, lon, lat

    photo_location_index = defaultdict(list)

    if photo_string is None: return photo_location_index

    for photo in photo_string.split(','):
        xxxx = get_photo_location(photo)
        if xxxx is None : continue

        p_dt, p_lon, p_lat = xxxx
        if is_mars_in_china:
            p_lon, p_lat = fix_mars_in_china((p_lon, p_lat))

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


if __name__ == '__main__':
    import loading
    timestamp_list, location_list = loading.load_gps_data(['./tuanpohu.gpx'])

    photo_render = PhotoRender('p.txt', timestamp_list, location_list)
    photo_render.debug()
