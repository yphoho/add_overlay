# gpx_video
Animate track point from gpx or fit file on map. Add photo and audio as needed.

1. Copy the json file in source to the *geotiler site-packages source* dir(something like: ~/.local/lib/python3.8/site-packages/geotiler/source/).
2. Call the *gpx_to_route.py* as in *a.sh*.



## howto show photo in the video
1. List the photo(or video) name in a file, and call the script as *--photo* arg;
2. The photo must have GPS info, or give the datetime after photo name just like what it is in *p.txt*;
3. The video clip must has datetime after the name;

## NOTE
For the reason you know, *In China* it must make some effort to access OpenStreetMap, GoogleMap and many other maps. The good message, map tile from Esri is reachable.
