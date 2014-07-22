#!/bin/bash
# prepare_hires_hydro.sh
# Description:  This script creates a set of high resolution hydrology files
#               for import into WRF-Hydro as the hires terrain parameters
#               using GRASS-GIS version 6.4
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
ncdump -h geo_em.d03.nc | grep corner
#        :corner_lats = 29.0575f, 35.0216f, 34.97108f, 29.01007f, 29.05748f, 35.02156f, 34.97061f, 29.00964f, 29.04401f, 35.03507f, 34.98454f, 28.9966f, 29.04399f, 35.03504f, 34.98409f, 28.99617f ;
#        :corner_lons = 33.27399f, 33.25964f, 37.17422f, 36.94519f, 33.25854f, 33.24319f, 37.19067f, 36.96063f, 33.27402f, 33.25961f, 37.1748f, 36.9447f, 33.25858f, 33.24316f, 37.19122f, 36.96014f ;
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
# using the llcorner coordinates obtained above
echo "33.27399,29.0575" | v.in.ascii in=- out=llcorner fs=, 

# Import the hydrostations shapefile
v.in.ogr dsn=~/geodata/IHS/combined_stations.shp output=stations

# Download relevant HydroSHED tiles:
# Get the 3-sec conditioned grids covering the region
# *** Change here for your region! *** #
for t in n25e030 n25e035 n30e30 n30e35 n35e30 n35e35; do \
    wget http://earlywarning.usgs.gov/hydrodata/sa_con_3s_grid/AF/${t}_con_grid.zip;
    unzip -n ${t}_con_grid.zip;
done
rm -f *.zip

# Import and Merge tiles (set region to the list of tiles)
for d in n*; do \
    tile=`basename $d _con`; r.in.gdal input=$d/$d/w001001.adf output=$tile; 
done
g.region -p rast=`g.mlist rast pat=n* sep=,`
r.patch input=`g.mlist rast pat=n* sep=,` output=hydrosheds_raw
# Remove individual tiles
g.mremove -f rast=n*


# Create a mask for land areas from the GSHHG data
# Download Global shoreline shapefiles 
wget http://www.soest.hawaii.edu/pwessel/gshhg/gshhg-shp-2.2.4.zip
unzip gshhg-shp-2.2.4.zip
# use the "high resolution" file (directory "h"), L1 (shorelines) and L2 (lakes)
# extract only europe, asia, africa land polygons, and clip out the lakes layer (L2) from land layer (L1)  
v.in.ogr dsn=GSHHS_shp/h/GSHHS_h_L1.shp out=land snap=0.001 min_area=10
v.in.ogr dsn=GSHHS_shp/h/GSHHS_h_L2.shp out=lakes snap=0.01
v.extract input=land output=eurasia list=1,3
v.overlay -t ain=eurasia atype=area bin=lakes btype=area out=eurasia_land operator=not
# Use the land polygon to make a raster mask
v.to.rast in=eurasia_land out=eurasia_mask use=val val=1

# Use the eurasia_mask raster to mask out DeadSea and Kinneret
r.mask eurasia_mask
r.mapcalc "hydrosheds_dem = hydrosheds_raw"
r.mask -r eurasia_mask

# cleanup...
g.remove -f vect=land,lakes


#---------------------------------------------------#
###  Now work in new LCC CRS  
#---------------------------------------------------#
# Exit GRASS and restart in new Lambert Conformal Conic LOCATION.
# This LOCATION should be defined to match the LCC projection used in your WRF model
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


# Set up for sqlite vector attribute tables
eval `g.gisenv`
echo $GISDBASE/$LOCATION_NAME/$MAPSET/
mkdir $GISDBASE/$LOCATION_NAME/$MAPSET/sqlite
db.connect driver=sqlite database=$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db
# Check database connection
db.connect -p
# driver:sqlite
# database:/home/micha/geodata/grass/WRF_LCC/Research/sqlite/sqlite.db
# schema:
# group:

# ReProject llcorner vector point and hydrosheds_dem to this LOCATION
v.proj input=llcorner location=WGS84 mapset=Research
# Here are the new coordinates of the lower left corner in LCC projection:
v.info -g llcorner
#south=-329067.32837467
#east=-21014.15540992

# Now edit the header lines of the AAIGrid raster created above
# Replace the xllcorner and yllcorner values with the projected point's x-y coordinates 
# and replace the cellsize with the geo_em.d03.nc resolution 
head -6 ascii/geo_em_hgt.asc
# ncols        120
# nrows        222
# xllcorner    -183913.850094574
# yllcorner    -327799.205939783
# cellsize     3000.000000000000
# NODATA_value  -9999

# Import the altered ASCII grid into GRASS
# and -o is necessary since the ASCII raster has no CRS definition
r.in.gdal -o ascii/geo_em_hgt.asc out=hgt

# Reproject the stations vector points layer
v.proj input=stations location=WGS84 mapset=Research output=stations

# Reproject the raster; first use the r.proj -g flag to set the necessary extents...
r.proj -g input=hydrosheds_dem location=WGS84 mapset=Research
# Input Projection Parameters:  +proj=longlat +no_defs +a=6378137 +rf=298.257223563 +towgs84=0.000,0.000,0.000
# Input Unit Factor: 1
# Output Projection Parameters:  +proj=lcc +lat_1=33.5 +lat_2=27.5 +lat_0=32.02967 +lon_0=33.49 +x_0=0 +y_0=0 +no_defs +a=6378137 +rf=298.257223563 +towgs84=0.000,0.000,0.000
# Output Unit Factor: 1
# Input map <hydrosheds_dem@Research> in location <WGS84>:
# n=904338.40797869 s=-773506.82226191 w=-353377.16385874 e=562777.78148445 rows=18000 cols=12000
# Use the last line of output to set the new region:
g.region -p n=904338.40797869 s=-773506.82226191 w=-353377.16385874 e=562777.78148445 rows=18000 cols=12000
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

# ... and do the actual reprojection
r.proj input=hydrosheds_dem location=WGS84 mapset=Research output=dem
#  ***  The result "dem" raster is the TOPOGRAPHY variable *** #

# Display the hgt raster together with the dem and stations point layer 
# to insure that everything is properly registered 
# Zoom in to about 1 pixel in the lowres (hgt) grid, 
# and verify that it covers 30x30 pixels in the hires (dem) grid
# (set color ramps for display)
r.colors hgt rule=grey
r.colors dem rule=srtm

# Now Set region to the extent of the geo_em "HGT" variable for the duration of the analysis 
# and double check that the resolution is 100m
g.region -p rast=hgt
g.region -p res=100




#---------------------------------------------------#
###  Watershed and stream network delineation   ###
#---------------------------------------------------#
# Run watershed module with threshold = 1000 (1000 cells of 100m = 1000 X 10,000 sq.m. = 10 sq.km.)
r.watershed elev=dem thresh=1000 accumulation=f_acc drainage=f_dir basin=bas stream=str
#  ***  The result "str" raster is the CHANNELGRID variable *** #

# For display convert stream raster to line vector
r.thin str output=str_thin
r.to.vect str_thin output=streams feature=line

# THe flow direction grid must be in the ArcGIS direction convention, so do a reclass
echo "1 -1 = 128
2 -2 = 64
3 -3 = 32
4 -4 = 16
5 -5 = 8
6 -6 = 4
7 -7 = 2
8 -8 = 1
*    = 255" > f_dir_reclass
r.reclass --o input=f_dir output=f_dir_arc rules=f_dir_reclass
#  ***  The result "f_dir_arc" raster is the FLOWDIRECTION      *** #

# Create stream order raster
# The set of r.stream.* GRASS addons are required here
r.stream.order --o stream=str dir=f_dir accum=f_acc strahler=str_order
#  *** The result "str_order" raster is the STREAMORDER variable *** #

# Snap the station locations to the stream network
v.db.addcol stations column="distance double precision"
v.distance --o from=stations to=streams output=tmp_connect upload=dist col=distance 
v.patch --o input=streams,tmp_connect out=tmp_streams
v.clean --o input=tmp_streams out=tmp_clean type=line tool=break error=tmp_snapped

# Use v.category to give cat values to each station (required for v.distance)
v.category --o tmp_snapped opt=add type=point out=snapped_stations
v.db.addtable map=snapped_stations column="station_id integer"
v.distance --o from=snapped_stations to=stations output=tmp_connect2 upload=to_attr column=station_id to_column=id
# Check that each snapped_station has it's station_id
v.db.select map=snapped_stations
# Double check visually by loading stations, streams, and snapped_stations, and verify 
# that the id's match and snapped_stations are indeed exactly on the stream network




# Convert snapped_stations to raster
# Use the station_id attrib as the raster value 
v.to.rast --o input=snapped_stations output=frxst_pts use=attr column=station_id
# *** The result raster "frxst_pts" is the frxst_pts variable *** #

# Create catchments for each station 
r.stream.basins dir=f_dir points=snapped_stations basins=catch
# The catchments are identified by the stream id, not (yet) by the station id
# Convert raster catchment to a polygon vector layer in order to add the station_id to each polygon
r.to.vect -s input=catch out=tmp_catchments feature=area
# Prepare polygon vector to patch together with the snapped_stations
v.db.addcol map=tmp_catchments column="station_id integer"
v.db.dropcol map=tmp_catchments column=value
v.db.dropcol map=tmp_catchments column=label
v.patch -e --o input=snapped_stations,tmp_catchments out=tmp_catchments2
# Now, after patching, remove the existing centroids, 
# and convert points (snapped_stations) to centroids
# This essentially gives each polygon (catchment) the value of the station_id from snapped_stations
v.edit map=tmp_catchments2 tool=delete type=centroid cats=0-9999
v.type input=tmp_catchments2 out=station_catchments type=point,centroid

# Now each catchment in "Station_catchments" has an id column which matches the station_id for it's pour point
# Display the snapped_stations point vector overlayed on the station_catchments raster
# to visually verify match between id in station_catchments layer and snapped_stations layer!

# Convert station_catchments back to raster for export to NetCDF 
# use the station_id attrib of the catchments as the raster category value
v.to.rast --o input=station_catchments output=station_catchments type=area use=attr column=station_id
# *** The resulting raster "station_catchments" is the basn_mask variable *** #

# Cleanup...
g.remove rast=catch
g.mremove -f vect=tmp*

#---------------------------------------------------#
###  Export data layers to AAIGrid format   ###
#---------------------------------------------------#
# Export rasters to AAIGrid for use in create_netcdf.py script
r.out.gdal -c --o -f in=dem out=ascii/topography.asc format=AAIGrid type=Int16 nodata=-9999
r.out.gdal -c --o in=f_dir_arc out=ascii/flowdir.asc format=AAIGrid type=Int16 createopt="DECIMAL_PRECISION=0" nodata=-9999
# Use Int32 datatype for streams, there may be more than 32767 stream reaches!
r.out.gdal -c --o in=str out=ascii/channelgrid.asc format=AAIGrid type=Int32 nodata=-9999
r.out.gdal -c --o in=str_order out=ascii/streamorder.asc format=AAIGrid type=Int16 nodata=-9999
r.out.gdal -c --o in=station_catchments out=ascii/basins.asc format=AAIGrid type=Int16 nodata=-9999
r.out.gdal -c --o in=frxst_pts out=ascii/frxstpts.asc format=AAIGrid type=Int16 nodata=-9999

# The ASCII grids have "cellsize = 100.000000000000" in the header rows.
# The python script for creating the NetCDF expects integer values
# Replace in all the above *.asc to "cellsize = 100"
for a in ascii/*.asc; do sed -i 's/100.000000000000/100/' $a; done
# check:
grep cellsize ascii/*.asc

# Get all other attributes from the original stations table to the new snapped_stations
# Start sqlite, open the mapset's sqlite db 
# and do UPDATE queries to upload all additional attribute columns to the snapped_stations data table
sqlite3 ~/geodata/grass/WRF_LCC/Research/sqlite/sqlite.db
# The following commands are entered at the sqlite prompt 
sqlite> ALTER TABLE snapped_stations ADD COLUMN station_num INTEGER;
sqlite> ALTER TABLE snapped_stations ADD COLUMN station_name varchar(64);
sqlite> ALTER TABLE snapped_stations ADD COLUMN latitude double precision;
sqlite> ALTER TABLE snapped_stations ADD COLUMN longitude double precision;
sqlite> ALTER TABLE snapped_stations ADD COLUMN reshut_num integer;
sqlite> ALTER TABLE snapped_stations ADD COLUMN reshut_name varchar(32);
sqlite> ALTER TABLE snapped_stations ADD COLUMN owner varchar(16);
sqlite> UPDATE snapped_stations SET station_num=(SELECT stat_num FROM stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET station_name=(SELECT stat_name FROM stations WHERE id=snapped_stations.station_id);
# No need to update longitude and latitude - we get those values *after* projecting back to WGS84 Lon/Lat CRS
sqlite> UPDATE snapped_stations SET reshut_num=(SELECT reshut_num FROM stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET reshut_nam=(SELECT reshut_nam FROM stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET owner=(SELECT owner FROM stations WHERE id=snapped_stations.station_id);
sqlite> select * from snapped_stations;
sqlite> .q


# Get latitude/longitude coordinates of snapped_stations:
# This requires shifting back to the WGS84 LOCATION
# Switch to WGS84 LOCATION, reproject the snapped_stations back to Lat/Lon CRS,
g.mapset location=WGS84 mapset=Research
v.proj --o input=snapped_stations location=WRF_LCC mapset=Research
# and then update Latitude and Longitude columns
v.to.db snapped_stations option=coor columns="longitude,latitude" units=degrees
# Output to a csv file
v.out.ascii -c --o input=snapped_stations out=ascii/stations.csv columns="station_id,station_num,station_name" separator=,

#-----------------------------------------------------#
###  Finished. Now run the create_netcdf.py script  ###
#-----------------------------------------------------#
