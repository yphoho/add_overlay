#!/usr/bin/env python
# -*- coding: utf-8 -*-
# yang @ 2023-09-08 22:54:45

import sys
import os

from collections import namedtuple
from datetime import datetime

from pathlib import Path

import bz2
import gzip
import lzma

import util


class Session(object):
    def __init__(self, dt, start_time, total_elapsed_time, total_moving_time, total_distance=0.0, total_ascent=0.0, max_speed=0.0, avg_speed=0.0):
        self.dt = dt
        self.start_time = start_time
        self.total_elapsed_time = total_elapsed_time / 3600
        self.total_moving_time = total_moving_time / 3600

        self.total_distance = total_distance / 1000
        self.total_ascent = total_ascent
        self.max_speed = max_speed * 3.6
        self.avg_speed = avg_speed * 3.6

    def __str__(self):
        return f'datetime:{self.dt}, start_time:{self.start_time}, total_elapsed_time:{self.total_elapsed_time}, total_moving_time:{self.total_moving_time}, total_distance:{self.total_distance}, total_ascent:{self.total_ascent}, max_speed:{self.max_speed}, avg_speed:{self.avg_speed}'

    def merge(self, b):
        self.dt = max(self.dt, b.dt)
        self.start_time = min(self.start_time, b.start_time)
        self.total_elapsed_time += b.total_elapsed_time
        self.total_moving_time += b.total_moving_time

        self.total_distance += b.total_distance
        self.total_ascent += b.total_ascent
        self.max_speed = max(self.max_speed, b.max_speed)
        self.avg_speed = self.total_distance / self.total_moving_time

    @staticmethod
    def merge_session(sess_list):
        if not sess_list: return None

        sess = sess_list[0]
        for s in sess_list[1:]:
            sess.merge(s)

        print(sess)

        return sess


def log(s):
    print(s, file=sys.stderr)

def fatal(s, error=True):
    log(s)
    exitcode = 1 if error else 0
    exit(exitcode)


def load_gps_data(filepath_list):
    timestamp, positions, sess_list = [], [], []
    for filepath in filepath_list:
        suffix = Path(filepath).suffix.lower()
        if suffix == ".gpx":
            t, p, sess = load_gpx_file(filepath)
        elif suffix == ".fit":
            t, p, sess = load_fit_file(filepath)
        else:
            fatal(f"Don't recognise filetype from {filepath} - support .gpx and .fit")

        timestamp.extend(t)
        positions.extend(p)
        sess_list.append(sess)

    sess = Session.merge_session(sess_list)

    return timestamp, positions, sess


FILE_OPENER = {
    'xz': lzma.LZMAFile,
    'bz2': bz2.BZ2File,
    'gz': gzip.GzipFile,
}

NAMESPACES = {
    'gpx': 'http://www.topografix.com/GPX/1/1',
}

def load_gpx_file_xxxx(filename):
    from lxml import etree

    get_attr = lambda n, a: float(n.get(a))
    get_point = lambda n: (get_attr(n, 'lon'), get_attr(n, 'lat'))

    _, ext = os.path.splitext(filename)
    ext = ext[1:]

    f_open = FILE_OPENER.get(ext, open)

    with f_open(filename) as f:
        tree = etree.parse(f)
        nodes = tree.xpath('//gpx:trkpt', namespaces=NAMESPACES)
        return (get_point(n) for n in nodes)


def load_gpx_file(filename):
    import gpxpy

    timestamp, lon, lat, alt = [], [], [], []
    speed, distance, cadence = [], [], []

    _, ext = os.path.splitext(filename)
    ext = ext[1:]
    f_open = FILE_OPENER.get(ext, open)

    with f_open(filename) as f:
        gpx = gpxpy.parse(f)

        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    timestamp.append(point.time)
                    lon.append(point.longitude)
                    lat.append(point.latitude)
                    alt.append(point.elevation)

    tz = util.get_tz(lon[0], lat[0])

    start_dt, end_dt = timestamp[0].astimezone(tz), timestamp[-1].astimezone(tz)
    total_elapsed_time = (end_dt - start_dt).seconds

    session = Session(end_dt, start_dt, total_elapsed_time, total_elapsed_time)

    return timestamp, zip(lon, lat), session


def load_fit_file(filename):
    from fit_tool.fit_file import FitFile
    from fit_tool.profile.messages.record_message import RecordMessage
    from fit_tool.profile.messages.session_message import SessionMessage

    timestamp, lon, lat, alt = [], [], [], []
    speed, distance, cadence = [], [], []
    session = None
    tz = None

    ff = FitFile.from_file(filename)
    for record in ff.records:
        message = record.message
        if isinstance(message, RecordMessage):
            if message.position_long is None or message.position_long > 179.9999: continue

            if tz is None: tz = util.get_tz(message.position_long, message.position_lat)

            timestamp.append(datetime.fromtimestamp(message.timestamp//1000).astimezone(tz))
            lon.append(message.position_long)
            lat.append(message.position_lat)
            alt.append(message.altitude)

            speed.append(message.speed)
            distance.append(message.distance)
            cadence.append(message.cadence)
        elif isinstance(message, SessionMessage):
            session = Session(datetime.fromtimestamp(message.timestamp//1000).astimezone(tz),
                    datetime.fromtimestamp(message.start_time//1000).astimezone(tz),
                    message.total_elapsed_time, message.total_moving_time,
                    message.total_distance, message.total_ascent, message.max_speed, message.avg_speed)

    # print(session)

    return timestamp, zip(lon, lat), session


if __name__ == '__main__':
    pass
