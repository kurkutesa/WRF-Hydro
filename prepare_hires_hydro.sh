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
        :corner_lats = 29.0575f, 35.0216f, 34.97108f, 29.01007f, 29.05748f, 35.02156f, 34.97061f, 29.00964f, 29.04401f, 35.03507f, 34.98454f, 28.9966f, 29.04399f, 35.03504f, 34.98409f, 28.99617f ;
        :corner_lons = 33.27399f, 33.25964f, 37.17422f, 36.94519f, 33.25854f, 33.24319f, 37.19067f, 36.96063f, 33.27402f, 33.25961f, 37.1748f, 36.9447f, 33.25858f, 33.24316f, 37.19122f, 36.96014f ;
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
echo "33.27399,29.0575" | v.in.ascii in=- out=llcorner separator=, 

# Import the hydrostations shapefile
v.in.ogr dsn=~/geodata/IHS/combined_stations.shp output=stations

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
r.patch input=`g.mlist rast pat=n* sep=,` output=hydroshed_raw
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
v.extract input=land output=eurasia cats=1,3
v.overlay -t ain=eurasia atype=area bin=lakes btype=area out=eurasia_land operator=not
# Use the land polygon to make a raster mask
v.to.rast in=eurasia_land out=eurasia_mask use=val val=1

# Use the eurasia_mask raster to mask out DeadSea and Kinneret
r.mask eurasia_mask
r.mapcalc "hydrosheds_dem = hydrosheds_raw"
r.mask -r eurasia_mask



#---------------------------------------------------#
###  Now work in new LCC CRS  
#---------------------------------------------------#
# Exit GRASS and restart in new Lambert Conformal Conic LOCATION.
# This LOCATION should be defined to match the LCC projection used in your WRF model
# Projection definition:
g.proj -p
#\-PROJ_INFO-------------------------------------------------
# name       : Lambert Conformal Conic
# proj       : lcc
# lat_1      : 33.5
# lat_2      : 29.5
# lat_0      : 32.02967
# lon_0      : 35.16205
# x_0        : 0
# y_0        : 0
# no_defs    : defined
# datum      : wgs84
# ellps      : wgs84
# -PROJ_UNITS------------------------------------------------
# unit       : meter
# units      : meters
# meters     : 1

# ReProject llcorner vector point and hydrosheds_dem to this LOCATION
v.proj input=llcorner location=WGS84 mapset=Research
# Here are the new coordinates of the lower left corner in LCC projection:
v.info -g llcorner
# north=-327799.205939783
# south=-327799.205939783
# east=-183913.850094574
# west=-183913.850094574

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
g.region `r.proj -g input=hydrosheds_dem location=WGS84 mapset=Research`
# ... and force resolution to exactly 100 m...
g.region -p -a res=100                                                                
# projection: 99 (Lambert Conformal Conic)
# zone:       0
# datum:      wgs84
# ellipsoid:  wgs84
# north:      897900
# south:      -780100
# west:       -523900
# east:       491000
# nsres:      100
# ewres:      100
# rows:       16780
# cols:       10149
# cells:      170300220
# ... and do the reprojection
r.proj input=hydrosheds_dem location=WGS84 mapset=Research output=dem
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




#---------------------------------------------------#
###  Watershed and stream network delineation   ###
#---------------------------------------------------#
# Run watershed module with threshold = 1000 (1000 cells of 100m = 1000 X 10,000 sq.m. = 10 sq.km.)
r.watershed -b elev=dem thresh=1000 accumulation=f_acc drainage=f_dir basin=bas stream=str
#  ***  The result "str" raster is the CHANNELGRID variable *** #
#  ***  The result "f_dir" raster is the FLOWDIRECTION      *** #

# For display convert stream raster to line vector
r.thin str output=str_thin
r.to.vect str_thin output=streams type=line

# Create stream order raster
# The set of r.stream.* GRASS addons are required here
r.stream.order streams=str dirs=f_dir accum=f_acc strahler=str_order
#  *** The result "str_order" raster is the STREAMORDER variable *** #

# Snap the station locations to the stream network
# The "radius" parameter is in number of cells, so 20=2000 meters
r.stream.snap input=stations out=snapped_stations streams=str radius=20
# Copy the station_id from stations to snapped_stations
v.db.addtable snapped_stations column="station_id integer"
# Use the upload trick with v.distance to get attributes into the "from" vector 
v.distance from=snapped_stations to=stations out=connectors upload=to_attr column=station_id to_column=id
g.remove vect=connectors
# Now "snapped_stations" has an attrib column with the correct  station ids


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
sqlite> ALTER TABLE snapped_stations ADD COLUMN reshut_nam varchar(32);
sqlite> ALTER TABLE snapped_stations ADD COLUMN owner varchar(16);
sqlite> UPDATE snapped_stations SET station_num=(SELECT stat_num FROM stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET station_name=(SELECT stat_name FROM stations WHERE id=snapped_stations.station_id);
# No need to update longitude and latitude - we get those values *after* projecting back to WGS84 Lon/Lat CRS
sqlite> UPDATE snapped_stations SET reshut_num=(SELECT reshut_num FROM stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET reshut_nam=(SELECT reshut_nam FROM stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET owner=(SELECT owner FROM stations WHERE id=snapped_stations.station_id);
sqlite> select * from snapped_stations;
sqlite> .q


# Convert snapped_stations to raster
# Use the station_id attrib as the raster value 
v.to.rast input=snapped_stations output=frxst_pts use=attr attrcolumn=station_id
# *** The result raster "frxst_pts" is the frxst_pts variable *** #

# Create catchments for each station 
r.stream.basins dirs=f_dir points=snapped_stations basins=catch
# The catchments are identified by the stream id, not (yet) by the station id
# Convert raster catchment to a polygon vector layer in order to add the station_id to each polygon
r.to.vect -s input=catch out=station_catchments type=area
v.db.addcolumn station_catchments col="station_id INTEGER"
# Again use v.distance to get a value from one attrib table to another
v.distance from=station_catchments to=snapped_stations out=connectors upload=to_attr column=station_id to_column=station_id
g.remove vect=connectors
# Now each catchment in "Station_catchments" has an id column which matches the station_id for it's pour point
# Display the snapped_stations point vector overlayed on the station_catchments raster
# to visually verify match between id in station_catchments layer and snapped_stations layer!

# Convert station_catchments back to raster for export to NetCDF 
# use the station_id attrib of the catchments as the raster category value
v.to.rast --o input=station_catchments output=station_catchments type=area use=attr attrcolumn=station_id
g.remove rast=catch
# *** The resulting raster "station_catchments" is the basn_mask variable *** #


#---------------------------------------------------#
###  Export data layers to AAIGrid format   ###
#---------------------------------------------------#
# Export rasters to AAIGrid for use in create_netcdf.py script
r.out.gdal -c --o -f in=dem out=ascii/topography.asc format=AAIGrid type=Int16 nodata=-9999
r.out.gdal -c --o in=f_dir out=ascii/flowdir.asc format=AAIGrid type=Int16 createopt="DECIMAL_PRECISION=0" nodata=-9999
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

# Get latitude/longitude coordinates of snapped_stations:
# Switch to WGS84 LOCATION, reproject the snapped_stations back to Lat/Lon CRS,
# and then update Latitude and Longitude columns
g.mapset location=WGS84 mapset=Research
v.proj --o input=snapped_stations location=WRF_LCC mapset=Research
v.to.db snapped_stations option=coor columns="longitude,latitude" units=degrees
# Output to a csv file
v.out.ascii -c --o input=snapped_stations out=ascii/stations.csv columns="station_id,station_num,station_name" separator=,


#-----------------------------------------------------#
###  Finished. Now run the create_netcdf.py script  ###
#-----------------------------------------------------#
