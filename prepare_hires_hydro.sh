#!/bin/bash
# prepare_hires_hydro.sh
# Description:  This script creates a set of high resolution hydrology files
#               for import into WRF-Hydro as the hires terrain parameters
#               using GRASS-GIS
# Author:       Micha Silver, Arava Drainage Authority
# Date:         2014/11/01
# Usage:        The script requires GRASS 7.0 as well as the set of r.stream.* plugins 
#               A point shapefile of hydrometric stations should be prepared in advance, 
#               referenced in a Long/Lat WGS84 projection.
#               
#               Two parameters should be choosen in advance: 
#               1) the "Agg_Factor" = an integer multiplier 
#               indicating the relation between the hires terrain data
#               and the lowres land surface data from WRF. 
#               Here it is 30: hires=100 m, and lowres=3000 m.
#               2) a threshold for the watershed analysis. 
#               This determines the minimum area that will be delineated as a catchment.
#               Here it is 1000. At resolution 100m, 1000 cells threshold = 10 sq.km
#
#               The elevation data is obtained from the HydroSHEDS USGS project 
#               Conditioned grids will be downloaded from http://earlywarning.usgs.gov/
#               The particular 5deg X 5deg tiles should be entered in the download step below
#               
#               The geo_em.do3.nc NetCDF file from the WRF preprosessing stage should be available in a "NetCDF" subdir 
#               The shapefile of original hydrostation locations "combined_stations.shp" should be available in a "shp" subdir 
#
#               Two GRASS Locations should be defined in advance: One referenced to EPSG:4326 (WGS84 Long/Lat)
#               LOCATION: WGS84, MAPSET: IHS
#               and the second in Lambert Conformal Conic, with the parameters:
#               Central Meridian, Latitude of Origin, Standard_Parallel_1 and Standard_Parallel_2 set 
#               to match the projection in the geo_em.d03.nc dataset 
#               LOCATION: LCC, MAPSET: IHS

# Revisions:	24/02/2014	export to Geotiff rather than ASCII ArcINFO format
#               1/03/2014       shifted the sqlite update to an external sql file
#               14/04/2013      removed all referenced to station_id
#               18/04/2014      changed the vector to raster function which creates the frxst_pts raster to use value 0 instead of the station_id            
#		24/07/2014	threshold of r.watershed set to 250 (2.5 sq.km.)


#---------------------------------------------------#
### Environment variables
#---------------------------------------------------#
WORKDIR=/home/micha/work/IHS
NETCDFDIR=/home/micha/GIS/netCDF
export WORKDIR NETCDFDIR
LCC_LOC=LCC
WGS_LOC=WGS84
WORK_MAPSET=IHS
export WORK_MAPSET LCC_LOC WGS_LOC
#
#               Two GRASS Locations should be defined in advance: One referenced to EPSG:4326 (WGS84 Long/Lat)
#               and the second in Lambert Conformal Conic, with the parameters:
#               Central Meridian, Latitude of Origin, Standard_Parallel_1 and Standard_Parallel_2 set 
#               to match the projection in the geo_em.d03.nc dataset 


#---------------------------------------------------#
### Prepare HGT_M layer from geo_gm NetCDF file 
#---------------------------------------------------#
# Get Lower Left coords of geo_gm.d03.nc dataset
cd NetCDF
ncdump -h $NETCDFDIR/geo_em.d03.nc | grep corner
		:corner_lats = 29.05753f, 35.02162f, 34.9711f, 29.01011f, 29.0575f, 35.02159f, 34.97064f, 29.00967f, 29.04403f, 35.03509f, 34.98457f, 28.99662f, 29.04401f, 35.03506f, 34.9841f, 28.99619f ;
		:corner_lons = 33.27399f, 33.25964f, 37.17422f, 36.94519f, 33.25854f, 33.24319f, 37.19067f, 36.96063f, 33.27402f, 33.25961f, 37.1748f, 36.94473f, 33.25858f, 33.24316f, 37.19122f, 36.96014f ;
# Lower left Corner center is: 33.27399,29.0575

# Create ArcInfo ASCII version of HGT_M NetCDF variable
gdalinfo geo_em.d03.nc | grep HGT_M
#  SUBDATASET_26_NAME=NETCDF:"NetCDF/geo_em.d03.nc":HGT_M
#  SUBDATASET_26_DESC=[1x222x120] HGT_M (32-bit floating-point)
gdal_translate -of AAIGrid -a_nodata -9999 NETCDF:"geo_em.d03.nc":HGT_M ../ascii/geo_em_hgt.asc
cd ..

#---------------------------------------------------#
### Begin in WGS84 lon/lat CRS
#---------------------------------------------------#
# Start GRASS in EPSG:4326 CRS and create new point vector
# Just to check...
g.mapset map=$WORK_MAPSET loc=$WGS_LOC

# Import the list of hydrostations from a csv file 
v.in.ascii --o input="$WORKDIR"/new_stations.csv out=stations separator=comma skip=1 x=3 y=4 columns="stat_num integer, stat_nam text, longitude double precision, latitude double precision,reshut_num integer,reshut_name text,owner text, area integer, ret_lt_2 integer,ret_2_5 integer, ret_5_10 integer, ret_10_25 integer, ret_25_50 integer, ret_50_100 integer, ret_gt_100 integer"

# Create a single point vector layer 
# using the llcorner coordinates obtained above
echo "33.27399,29.05753" | v.in.ascii in=- out=llcorner separator=, 

# Download relevant HydroSHED tiles:
# Get the 3-sec conditioned grids covering the region
# *** Change here for your region! *** #
for t in n25e030 n25e035 n30e30 n30e35 n35e30 n35e35; do \
    wget http://earlywarning.usgs.gov/hydrodata/sa_con_3s_grid/AF/${t}_con_grid.zip;
    unzip ${t}_con_grid.zip;
done

# Import and Merge tiles (set region to the list of tiles)
for d in n*; do \
    tile=`basename $d _con`; r.in.gdal input=$d/$d/w001001.adf output=$tile; 
done
g.region -p rast=`g.mlist rast pat=n* sep=,`
r.patch input=`g.mlist rast pat=n* sep=,` output=hydrosheds_raw
# Remove individual tiles
g.mremove -f type=rast pattern=n*


# Create a mask for land areas from the GSHHG data
# Download Global shoreline shapefiles 
wget http://www.soest.hawaii.edu/pwessel/gshhg/gshhg-shp-2.2.4.zip
unzip gshhg-shp-2.2.4.zip
# use the "high resolution" file (directory "h"), L1 (shorelines) and L2 (lakes)
# extract only europe, asia, africa land polygons, and clip out the lakes layer (L2) from land layer (L1)  
v.in.ogr dsn=GSHHS_shp/h/GSHHS_h_L1.shp out=land snap=0.001 min_area=10
v.in.ogr dsn=GSHHS_shp/h/GSHHS_h_L2.shp out=lakes snap=0.01
v.extract input=land output=eurasia cats=1,3
v.overlay -t ain=eurasia atype=area bin=lakes btype=area out=eurasia_land operator=not
# Use the land polygon to make a raster mask
v.to.rast --o in=eurasia_land out=eurasia_mask use=val val=1

# Use the eurasia_mask raster to mask out DeadSea and Kinneret
r.mask eurasia_mask
r.mapcalc "hydrosheds_dem = hydrosheds_raw"
r.mask -r eurasia_mask


#---------------------------------------------------#
###  Now work in new LCC CRS  
#---------------------------------------------------#
# This LOCATION should be defined to match the LCC projection used in your WRF model
g.mapset --verbose map="$WORK_MAPSET" location="$LCC_LOC"
# Projection definition:
g.proj -p
#-PROJ_INFO-------------------------------------------------
#name       : Lambert Conformal Conic
#proj       : lcc
#lat_1      : 33.5
#lat_2      : 29.5
#lat_0      : 32.02967
#lon_0      : 33.49
#x_0        : 0
#y_0        : 0
#no_defs    : defined
#datum      : wgs84
#ellps      : wgs84
#-PROJ_UNITS------------------------------------------------
#unit       : meter
#units      : meters
#meters     : 1


# ReProject llcorner vector point and hydrosheds_dem to this LOCATION
v.proj input=llcorner location=$WGS_LOC mapset=$WORK_MAPSET

# Here are the new coordinates of the lower left corner in LCC projection:
v.info -g llcorner
#north=-329362.141647986
#south=-329362.141647986
#east=-21042.3232390716
#west=-21042.3232390716

# Now edit the header lines of the AAIGrid raster created above
# Replace the xllcorner and yllcorner with xllcenter and yllcenter
# Replace the values with the projected point's x-y coordinates 
# and replace the cellsize with the geo_em.d03.nc resolution (3000 m)
# After editing:
head -6 geo_em_hgt.asc
# ncols        120
# nrows        222
#xllcenter    -21042.6091447204
#yllcenter    -326070.772386501
#cellsize     3000.000000000000
# NODATA_value  -9999

# Import the *altered* ASCII grid into GRASS
# and -o is necessary since the ASCII raster has no CRS definition
cd $NETCDFDIR
r.in.gdal -o --o geo_em_hgt.asc out=hgt
cd $WORKDIR

# Reproject the stations vector points layer
v.proj --o input=stations location=$WGS_LOC mapset=$WORK_MAPSET output=stations

# Reproject the raster; first use the r.proj -g flag to set the necessary extents...
g.region `r.proj -g input=hydrosheds_dem location="$WGS_LOC" mapset="$WORK_MAPSET"`
# ... and force resolution to exactly 100 m...
g.region -p -a res=100                                                                
#projection: 99 (Lambert Conformal Conic)
#zone:       0
#datum:      wgs84
#ellipsoid:  wgs84
#north:      904100
#south:      -780100
#west:       -354300
#east:       660500
#nsres:      100
#ewres:      100
#rows:       16842
#cols:       10148
#cells:      170912616

# ... and do the reprojection
r.proj input=hydrosheds_dem location="$WGS_LOC" mapset="$WORK_MAPSET" output=dem
#  ***  The result "dem" raster is the TOPOGRAPHY variable *** #

# Display the hgt raster together with the dem and stations point layer 
# to insure that everything is properly registered 
# Zoom in to about 1 pixel in the lowres (hgt) grid, 
# and verify that it covers 30x30 pixels in the hires (dem) grid
# (set color ramps for display)
r.colors hgt rule=grey
r.colors dem rule=srtm
# Now Set region to the extent of the new dem for the duration of the analysis 
# and verify that the resolution is 100m !
g.region -p rast=hgt
g.region -p res=100
#projection: 99 (Lambert Conformal Conic)
#zone:       0
#datum:      wgs84
#ellipsoid:  wgs84
#north:      336637.859
#south:      -329362.141
#west:       -21042.323
#east:       338957.677
#nsres:      100
#ewres:      100
#rows:       6660
#cols:       3600
#cells:      23976000

#---------------------------------------------------#
###  Watershed and stream network delineation   ###
#---------------------------------------------------#
# Run watershed module with threshold = 250 (250 cells of 100m = 250 X 10,000 sq.m. = 2.5 sq.km.
# Use the -s option (SFD) to copy ArcMap's FLOW DIRECTION method
r.watershed -s -b --o elev=dem thresh=250 accumulation=f_acc drainage=f_dir basin=bas stream=str
#  ***  The result "str" raster is the CHANNELGRID variable *** #

# For display convert stream raster to line vector
r.thin --o str output=str_thin
r.to.vect --o str_thin output=streams type=line

# THe flow direction grid must be in the ArcGIS direction convention, so do a reclass
echo "1 -1 = 128
2 -2 = 64
3 -3 = 32
4 -4 = 16
5 -5 = 8
6 -6 = 4
7 -7 = 2
8 -8 = 1
*    = 255" > "$WORKDIR"/fdir_reclass.txt

r.reclass --o input=f_dir output=f_dir_arc rules="$WORKDIR"/fdir_reclass.txt
#  ***  The result "f_dir_arc" raster is the FLOWDIRECTION      *** #

# Create stream order raster
# The set of r.stream.* GRASS addons are required here
r.stream.order --o stream_rast=str direction=f_dir accum=f_acc strahler=str_order
#  *** The result "str_order" raster is the STREAMORDER variable *** #

# Snap the station locations to the stream network
# The "radius" parameter is in number of cells, so 20=2000 meters
r.stream.snap --o input=stations out=snapped_stations stream_rast=str accum=f_acc radius=20
# Copy the station_id from stations to snapped_stations
v.db.addtable snapped_stations column="stat_num integer"
# Use the upload trick with v.distance to get attributes into the "from" vector 
v.distance from=snapped_stations to=stations out=connectors upload=to_attr column=stat_num to_column=stat_num
g.remove vect=connectors
# Now "snapped_stations" has an attrib column with the correct station ids
# Display stations and snapped_stations vectors, with station_id, and verify that they match

# Convert snapped_stations to raster
# Set the pixel value at each station (pour point) to zero, as required by WRF-Hydro
v.to.rast --o input=snapped_stations output=frxst_pts use=col attrcol=stat_num
# *** The result raster "frxst_pts" is the frxst_pts variable *** #


# Create catchments for each station 
r.stream.basins --o direction=f_dir points=snapped_stations basins=catch
# The catchments are identified by the stream id, not (yet) by the station number
# Convert raster catchment to a polygon vector layer in order to add the stat_num to each polygon
r.to.vect -s --o input=catch out=station_catchments type=area
v.db.addcolumn station_catchments col="stat_num INTEGER"
# Again use v.distance to get a value from one attrib table to another
v.distance from=station_catchments to=snapped_stations out=connectors upload=to_attr column=stat_num to_column=stat_num
g.remove vect=connectors
# Now each catchment in "Station_catchments" has a stat_num column which matches the stat_num for it's pour point

# Display the snapped_stations point vector overlayed on the station_catchments raster
# to visually verify match between id in station_catchments layer and snapped_stations layer!

# Convert station_catchments back to raster for export to NetCDF 
# use the station_id attrib of the catchments as the raster category value
#v.to.rast --o input=station_catchments output=station_catchments type=area use=attr attrcolumn=stat_num
v.to.rast --o input=station_catchments output=station_catchments type=area use=cat
g.remove rast=catch
# *** The resulting raster "station_catchments" is the basn_mask variable *** #

# Make the OVROUGHRTFAC raster with value 1 throughout
r.mapcalc --o "ovrough = 1"

#-------------------------------------------#
###  Export data layers to GTiff format   ###
#-------------------------------------------#
# Export rasters to GTiff for use in create_netcdf.py script
mkdir -p "$WORKDIR"/gtiff
r.out.gdal -c --o -f in=dem out="$WORKDIR"/gtiff/TOPOGRAPHY.tif format=GTiff type=Int16 createopt="COMPRESS=LZW" nodata=-9999
r.out.gdal -c --o in=f_dir_arc out="$WORKDIR"/gtiff/FLOWDIRECTION.tif format=GTiff type=Int16 createopt="COMPRESS=LZW" nodata=-9999 
# Use Int32 datatype for streams, there may be more than 32767 stream reaches!
r.out.gdal -c --o in=str out="$WORKDIR"/gtiff/CHANNELGRID.tif format=GTiff type=Int32 createopt="COMPRESS=LZW" 
r.out.gdal -c --o in=str_order out="$WORKDIR"/gtiff/STREAMORDER.tif format=GTiff type=Int16 createopt="COMPRESS=LZW" nodata=-9999
r.out.gdal -c --o in=station_catchments out="$WORKDIR"/gtiff/basn_mask.tif format=GTiff type=Int16 createopt="COMPRESS=LZW" nodata=-9999
r.out.gdal -c --o in=frxst_pts out="$WORKDIR"/gtiff/frxst_pts.tif format=GTiff type=Int16 createopt="COMPRESS=LZW" nodata=-9999
# For OVROUGHRTFAC the default value everywhere should be 1
r.out.gdal -c --o in=ovrough out="$WORKDIR"/gtiff/OVROUGHRTFAC.tif format=GTiff type=Int16 createopt="COMPRESS=LZW" nodata=1


#---------------------------------------------------#
###  Export stations as CSV file with Long/Lat    ###
#---------------------------------------------------#
# Switch back to WGS84 LOCATION, reproject the snapped_stations back to Lat/Lon CRS,
# Update all data fields
# Get latitude/longitude coordinates of snapped_stations and update Latitude and Longitude columns
g.mapset location="$WGS_LOC" mapset="$WORK_MAPSET"

v.proj --o input=snapped_stations location="$LCC_LOC" mapset="$WORK_MAPSET"
v.proj --o input=station_catchments location="$LCC_LOC" mapset="$WORK_MAPSET"
v.proj --o input=streams location="$LCC_LOC" mapset="$WORK_MAPSET"
# Start sqlite, open the mapset's sqlite db 
# and do UPDATE queries to upload all additional attribute columns to the snapped_stations data table
# To find the location of the sqlite.db file, run db.connect -p
DB=`db.connect -p | grep database | awk -F: '{print $2}'`
# Now run the sql script to add columns and updates the rows
sqlite3 $DB < "$WORKDIR"/update_stations.sql

# Also add longitude/latitude column values
v.to.db snapped_stations option=coor columns="lon,lat" units=degrees
# Output to a csv file and shapefiles of streams, stations and catchments
mkdir -p "$WORKDIR"/shp
rm -f "$WORKDIR"/shp/snapped_stations.*
rm -f "$WORKDIR"/shp/station_catchments.*
rm -f "$WORKDIR"/shp/streams.*

v.out.ascii -c --o input=snapped_stations out="$WORKDIR"/shp/snapped_stations.csv columns="stat_num,stat_name,stat_he,reshut_num,reshut_nam,owner,ret_lt_2,ret_2_5,ret_5_10,ret_10_25,ret_25_50,ret_50_100,ret_gt_100" separator=,
v.out.ogr -e -s snapped_stations dsn="$WORKDIR"/shp/snapped_stations.shp type=point
v.out.ogr -e -s station_catchments dsn="$WORKDIR"/shp/station_catchments.shp type=area
v.out.ogr -e -s streams dsn="$WORKDIR"/shp/streams.shp type=line

#-----------------------------------------------------#
###  Finished. Now run the create_netcdf.py script  ###
#-----------------------------------------------------#
# i.e.
# python "$WORKDIR"/scripts/Thomas/create_hires_v2.py -d 3600 6660 $NETCDFDIR/gis_hires.nc "$WORKDIR"/gtiff
