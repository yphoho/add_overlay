#!/usr/bin/env python
# -*- coding: utf-8 -*-
# yang @ 2023-09-13 16:23:08

## https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Lon..2Flat._to_tile_numbers_2

## tile server
# https://leaflet-extras.github.io/leaflet-providers/preview/
# https://raw.githubusercontent.com/AliFlux/MapTilesDownloader/master/src/UI/main.js
# https://github.com/zhengjie9510/google-map-downloader


import sys

import math


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def num2deg(xtile, ytile, zoom):
    n = 1 << zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


if __name__ == '__main__':
    zoom = int(sys.argv[1]) if len(sys.argv) > 1 else 16

    lon, lat = 117.1906400, 39.1030400
    x, y = deg2num(lat, lon, zoom)
    print(x, y)

    print('http://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{0}/{2}/{1}'.format(zoom, x, y))
    # print('http://server.arcgisonline.com/ArcGIS/rest/services/World_Physical_Map/MapServer/tile/{0}/{2}/{1}'.format(zoom, x, y))
    # print('https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{0}/{2}/{1}'.format(zoom, x, y))

    # print('https://map1.vis.earthdata.nasa.gov/wmts-webmerc/MODIS_Terra_CorrectedReflectance_TrueColor/default/GoogleMapsCompatible_Level9/{0}/{2}/{1}.jpg'.format(zoom, x, y))

    # m for map;
    # s for satellite;
    # y for satellite with label;
    # t for terrain;
    # p for terrain with label;
    # h for label;
    print('https://mt0.google.com/vt?lyrs=m&x={1}&s=&y={2}&z={0}'.format(zoom, x, y)) # google map
    print('https://mt0.google.com/vt?lyrs=s&x={1}&s=&y={2}&z={0}'.format(zoom, x, y)) # google map satellite
    print('https://mt0.google.com/vt?lyrs=y&x={1}&s=&y={2}&z={0}'.format(zoom, x, y)) # google map satellite with label
    # print('https://mt0.google.com/vt?lyrs=t&x={1}&s=&y={2}&z={0}'.format(zoom, x, y)) # google map terrain
    print('https://mt0.google.com/vt?lyrs=p&x={1}&s=&y={2}&z={0}'.format(zoom, x, y)) # google map terrain with label
    print('https://mt0.google.com/vt?lyrs=h&x={1}&s=&y={2}&z={0}'.format(zoom, x, y)) # label

    # http://mts0.googleapis.com/vt?lyrs={style}&x={x}&y={y}&z={z}
    # http://mt2.google.cn/vt/lyrs={style}&hl=zh-CN&gl=CN&src=app&x={x}&y={y}&z={z}
