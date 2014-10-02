#!/bin/bash
# Description:	GRASS script to read a CVS formatted file of gridded precip data
#		and create a precipitation raster
#		Some vector layers are overlayed, and a png map image is exported
# Author:	Micha Silver
# Date:		2/10/2014
# Parameters:	
inputdir=$1
outputdir=$2
if [[ -z $inputdir ]]; then
	echo "Syntax $0 <directory of csv files for input> <directory for png output>"
	exit
fi  
if [[ -z $outputdir ]]; then
	outpurdir="."
fi

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
p=`ls $inputdir/precip*.txt | head -1`
reg=`r.in.xyz -s -g input=${p} output=dummy fs=, |  awk '{print $1" "$2" "$3" "$4}'`
g.region --q $reg
# Also set resolution to 1/30 degree (about 3 km)
g.region --q res=0.033

# Loop thru input directory
for f in $inputdir/precip*.txt; do
	precip_rast=`basename ${f} .txt`
	r.in.xyz --quiet --overwrite input=${f} output=$precip_rast fs=, method=mean
	r.null $precip_rast setnull=0
	r.colors --quiet $precip_rast rules=precip_color_rules
	export GRASS_PNGFILE=${outputdir}/${precip_rast}.png
	d.mon --quiet start=PNG
	# Add layers
	d.rast --quiet $precip_rast
	d.vect --quiet water_bodies@precip type=boundary color="160:200:225"
	d.vect --quiet border_il@precip type=boundary
	d.vect --quiet mideast_cities@precip type=point display=shape,attr icon=basic/point size=8 color=orange attrcol=name lcolor=orange lsize=6
	title=`echo $precip_rast | sed s'/precip_csv_//'`
	d.text.freetype --quiet -b at="4,96" text="${title}" size=3 color=black bgcolor=white
	d.legend -s --q map=${precip_rast} at="2,25,88,95" range=1,100
	d.mon --quiet stop=PNG
done

# run GRASS' cleanup routine
$GISBASE/etc/clean_temp

# remove session tmp directory:
rm -rf /tmp/grass6-$USER-$GIS_LOCK

# Create animation
convert -delay 5 -loop 0 -dispose Background ${outputdir}/*.png ${outputdir}/$precip_rast_anim.gif

