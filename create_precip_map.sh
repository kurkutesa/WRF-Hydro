#!/bin/bash
# Description:	GRASS script to read a CVS formatted file of gridded precip data
#		and create a precipitation raster
#		Some vector layers are overlayed, and a png map image is exported
# Author:	Micha Silver
# Date:		2/10/2014
# Parameters:	

# Set up GRASS environment
export GISBASE=/usr/lib/grass64
export PATH=$PATH:$GISBASE/bin:$GISBASE/scripts
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$GISBASE/lib
export GIS_LOCK=$$

export GISDBASE=/home/micha/GIS/grass
export LOCATION_NAME=WGS84
export MAPSET=precip
#GRASS_GUI=wxpython
export GRASS_WIDTH=400
export GRASS_HEIGHT=600
export GRASS_TRUECOLOR=TRUE

# Get one input file and set region
p=`ls $inputdir/precip*.txt | head 1`
reg=`r.in.xyz -s -g input=${p} output=dummy fs=,`
g.region --q $reg
# Also set resolution to 1/30 degree (about 3 km)
g.region --q res=0.033

# Loop thru input directory
for f in $inputdir/precip*.txt; do
	precip_rast=`basename ${f} .txt`
	r.in.xyz input=${f} output=$precip_rast fs=, method=mean
	r.null $precip_rast setnull=0
	r.colors $precip_rast rules=precip_color_rules
	export GRASS_PNGFILE=${precip_rast}.png
	d.mon start=PNG
	# Add layers
	d.rast $precip_rast
	d.vect water_bodies type=boundary color="160:200:225"
	d.vect border_il type=boundary
	d.vect mideast_cities type=point display=shape,attr icon=basic/point size=8 color=orange attrcol=name lcolor=orange lsize=6
	d.mon stop=PNG
done

# run GRASS' cleanup routine
$GISBASE/etc/clean_temp

# remove session tmp directory:
rm -rf /tmp/grass6-$USER-$GIS_LOCK

