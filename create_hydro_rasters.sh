#!/bin/bash
# Download ASTER_GDEM tiles from http://gdex.cr.usgs.gov/gdex/ (requires registration)
# ASTGTM2_N28E034_dem.tif  ASTGTM2_N29E036_dem.tif  ASTGTM2_N31E036_dem.tif  ASTGTM2_N34E034_dem.tif  ASTGTM2_N35E036_dem.tif
# ASTGTM2_N28E035_dem.tif  ASTGTM2_N30E034_dem.tif  ASTGTM2_N32E034_dem.tif  ASTGTM2_N34E035_dem.tif  ASTGTM2_N35E037_dem.tif
# ASTGTM2_N28E036_dem.tif  ASTGTM2_N30E035_dem.tif  ASTGTM2_N32E035_dem.tif  ASTGTM2_N34E036_dem.tif
# ASTGTM2_N28E037_dem.tif  ASTGTM2_N30E036_dem.tif  ASTGTM2_N32E036_dem.tif  ASTGTM2_N34E037_dem.tif
# ASTGTM2_N29E034_dem.tif  ASTGTM2_N31E034_dem.tif  ASTGTM2_N33E035_dem.tif  ASTGTM2_N35E034_dem.tif
# ASTGTM2_N29E035_dem.tif  ASTGTM2_N31E035_dem.tif  ASTGTM2_N33E036_dem.tif  ASTGTM2_N35E035_dem.tif


### Get data into GRASS in Latitude/Longitude LOCATION ###
#--------------------------------------------------------#
# Start GRASS in WGS84 LOCATION (EPSG:4326) and import tif files
for f in *dem.tif; do \
    tile=`basename $f _dem.tif | sed 's/ASTGTM2_//'` ; 
    r.in.gdal input=$f output=$tile; \
done
# Set region and merge all tiles
g.region -p rast=`g.mlist rast pat=N* sep=,`
r.patch in=`g.mlist rast pat=n* sep=,` out=aster_raw

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

# Get the combined hydrostations layer
v.in.ogr dsn=combined_stations.shp out=combined_stations


###   Re project data to Israel Transverse Mercator    ###
#--------------------------------------------------------#
# close and restart GRASS in Israel Transverse Mercator LOCATION
# Reproject layers from WGS84 to ITM
# First find region parameters to cover the whole ASTER DEM area
r.proj -g in=aster_raw loc=WGS84 map=Research
g.region -p n=1103622.2529739 s=212896.11729703 w=100972.39445256 e=494489.96717272 rows=28801 cols=14401
# Set resolution to 100m. and do the reprojections
g.region -a -p res=100
r.proj input=aster_raw location=WGS84 mapset=Research method=cubic_f
r.proj input=eurasia_mask location=WGS84 mapset=Research method=cubic_f
v.proj input=combined_stations location=WGS84 mapset=Research

# Further Reduce the region to cover only the drainage areas that flow into Israel
g.region -p n=870000 e=380000 w=108000 s=270000

# Make the dem with Dead Sea and Kinneret set to NULL
r.mask eurasia_mask
r.mapcalc "dem = aster_raw"
### === The resulting "dem" raster is the TOPOGRAPHY === ###

r.mask -r eurasia_mask
# Create color ramp and shaded relief for nice map view
r.shaded.relief input=dem out=dem_shade azimuth=315 zmult=2
r.colors dem rule=~/work/IHS/GIS/my_srtm.rules

###    Watershed and stream network delineation    ###
#--------------------------------------------------------#
# Run watershed module with threshold = 1000 (1000 cells of 100m = 1000 X 10,000 sq.m. = 10 sq.km.)
r.watershed -b elev=dem thresh=1000 accumulation=f_acc drainage=f_dir basin=bas stream=str
### ===  The result "str" raster is the CHANNELGRID variable ===###
### ===  The result "f_dir" raster is the FLOWDIRECTION      ===###

r.thin str output=str_thin
r.to.vect str_thin output=streams type=line
# Create stream order raster
r.stream.order streams=str dirs=f_dir accum=f_acc strahler=str_order
# The result "str_order" raster is the STREAMORDER


### Snap the hydro-station locations to the stream network ###
#--------------------------------------------------------#
# Snap the station locations to the stream network
r.stream.snap input=combined_stations out=snapped_stations streams=str radius=10
# Copy the station_id from combined_stations to snapped_stations
v.db.addtable snapped_stations column="station_id integer"
# Use the upload trick with v.distance to get attributes into the "from" vector 
v.distance from=snapped_stations to=combined_stations out=connectors upload=to_attr column=station_id to_column=id
g.remove vect=connectors

# Start sqlite, open the mapset sqlite db 
# and upload all additional attribute columns to the snapped_stations data table
sqlite3 ~/geodata/grass/ITM/Research/sqlite/sqlite.db 
sqlite> ALTER TABLE snapped_stations ADD COLUMN stat_num INTEGER;
sqlite> ALTER TABLE snapped_stations ADD COLUMN stat_name varchar(64);
sqlite> ALTER TABLE snapped_stations ADD COLUMN ycoord double precision;
sqlite> ALTER TABLE snapped_stations ADD COLUMN xcoord double precision;
sqlite> ALTER TABLE snapped_stations ADD COLUMN latitude double precision;
sqlite> ALTER TABLE snapped_stations ADD COLUMN longitude double precision;
sqlite> ALTER TABLE snapped_stations ADD COLUMN reshut_num integer;
sqlite> ALTER TABLE snapped_stations ADD COLUMN reshut_nam varchar(32);
sqlite> ALTER TABLE snapped_stations ADD COLUMN owner varchar(16);
sqlite> UPDATE snapped_stations SET stat_num=(SELECT stat_num FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET stat_name=(SELECT stat_name FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET ycoord=(SELECT ycoord FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET xcoord=(SELECT xcoord FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET latitude=(SELECT latitude FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET longitude=(SELECT longitude FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET reshut_num=(SELECT reshut_num FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET reshut_nam=(SELECT reshut_nam FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> UPDATE snapped_stations SET owner=(SELECT owner FROM combined_stations WHERE id=snapped_stations.station_id);
sqlite> select * from snapped_stations;
sqlite> .q

# Convert snapped_stations to raster
v.to.rast input=snapped_stations output=frxst_pts use=attr attrcolumn=station_id
### === The resulting raster "frxst_pts" is the frxst_pts variable ===###



### Create drainage catchment for each station location ###
#---------------------------------------------------------#
# Create catchments for each station 
r.stream.basins dirs=f_dir points=snapped_stations basins=catch
# The catchments are identified by the stream id, not (yet) by the station id
# Convert raster catchment to a polygon vector layer in order to add the station_id to each polygon
r.to.vect -s input=catch out=station_catchments type=area
v.db.addcolumn station_catchments col="station_id INTEGER"
# Again use v.distance to get a value from one attrib table to another
v.distance from=station_catchments to=snapped_stations out=connectors upload=to_attr column=station_id to_column=station_id
g.remove vect=connectors
# Visually verify match between id in station_catchments layer and snapped_stations layer!
# Convert station_catchments back to raster for exprot to AAIGrid format for WRF
v.to.rast --o input=station_catchments output=station_catchments type=area use=attr attrcolumn=station_id
### === The resulting raster "station_catchments is the basn_mask variable ===###

### Export rasters to AAIGrid for use in create_netcdf.py script ###
#------------------------------------------------------------------#
r.out.gdal --o in=dem out=ascii/topography.asc format=AAIGrid type=Float32 -9999
r.out.gdal --o in=f_dir out=ascii/flowdirection.asc format=AAIGrid type=Int32 -9999
r.out.gdal --o in=str out=ascii/channelgrid.asc format=AAIGrid type=Int32 nodata=-9999
r.out.gdal --o in=str_order out=ascii/streamorder.asc format=AAIGrid type=Int32 nodata=-9999
r.out.gdal --o in=station_catchments out=ascii/basin.asc format=AAIGrid type=Int32 nodata=-9999
r.out.gdal --o in=frxst_pts out=ascii/frxstpts.asc format=AAIGrid type=Int32 nodata=-9999


