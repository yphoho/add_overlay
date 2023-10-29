target_png = ${target}.png
target_route = ${target}.route.mp4


all: ${target}

${target}: gpx_to_route.py util.py loading.py p.txt run.sh
	rm -f ${target} ${target_route}

clean:
	rm -f ${target} ${target_route} ${target_png}


.PHONY: all clean
