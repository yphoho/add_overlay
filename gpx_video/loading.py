#!/usr/bin/env python
# -*- coding: utf-8 -*-
# yang @ 2023-09-08 22:54:45

import sys
import os

from datetime import datetime

from pathlib import Path

import bz2
import gzip
import lzma


tzinfo = datetime.now().astimezone().tzinfo


def log(s):
    print(s, file=sys.stderr)

def fatal(s, error=True):
    log(s)
    exitcode = 1 if error else 0
    exit(exitcode)


def load_gps_data(filepath_list):
    timestamp, positions = [], []
    for filepath in filepath_list:
        suffix = Path(filepath).suffix.lower()
        if suffix == ".gpx":
            t, p = load_gpx_file(filepath)
            timestamp.extend(t)
            positions.extend(p)
        elif suffix == ".fit":
            t, p = load_fit_file(filepath)
            timestamp.extend(t)
            positions.extend(p)
        else:
            fatal(f"Don't recognise filetype from {filepath} - support .gpx and .fit")

    return timestamp, positions


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

    return timestamp, zip(lon, lat)


def load_fit_file(filename):
    from fit_tool.fit_file import FitFile
    from fit_tool.profile.messages.record_message import RecordMessage

    timestamp, lon, lat, alt = [], [], [], []
    speed, distance, cadence = [], [], []

    ff = FitFile.from_file(filename)
    for record in ff.records:
        message = record.message
        if not isinstance(message, RecordMessage): continue

        timestamp.append(datetime.fromtimestamp(message.timestamp//1000).replace(tzinfo=tzinfo))
        lon.append(message.position_long)
        lat.append(message.position_lat)
        alt.append(message.altitude)

        speed.append(message.speed)
        distance.append(message.distance)
        cadence.append(message.cadence)

    return timestamp, zip(lon, lat)


if __name__ == '__main__':
    pass
