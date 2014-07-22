#!/usr/bin/env python

'''
Description:  This script creates a set of high resolution hydrology files
              for import into WRF-Hydro as the hires terrain parameters
              using GRASS-GIS
Author:       Micha Silver, Arava Drainage Authority
Date:         2014/05/15
Requirements: The script requires GRASS 7.0 as well as the set of r.stream.* plugins 
              Python 2.7 is required.
              The Python NetCDF4 librfary
              The nc tools (ncdump) 
              GDAL
              A csv file of hydrometric station locations should be prepared in advance, 
              with X and Y coordinates referenced in a Long/Lat WGS84 projection.
               
Usage:      The GRASS location wizard should be used to make two GRASS LOCATIONs,
            one in WGS Longitude/Latitude (EPSG:4326) Coordinate Rerference System
            and the second using the Lambert Conformal Conic parameters suitable for your region:
            Central Meridian, Latitude of Origin, Standard_Parallel_1 and Standard_Parallel_2 set 
            to match the projection in the geo_em.d03.nc dataset 

            This python script takes two command line parameters:

            -d [--download-dem] indicates to download Digital Elevation Model tiles
            suitable for the region of the geo_em.d03 file. The tiles are downloaded
            from the HydroSHEDS website. If this option is omitted, then no files will be downloaded
            and you should already have a suitable GRASS elevation raster, named dem in the WGS84 location.
            This option is useful for repeated runs of the script, 
            to avoid downloading and processing the elevation tiles over and over. 

            -c [--config-file] used to specify an alternate location for the prepare_hires.conf 
            configuration file. This file contains a list of options used by the script.
            The default location is the same directory as the script itself.

Revisions:
'''

import os, sys, ConfigParser, argparse, math
from grass.script import grass
import netCDF4, numpy as np
from osgeo import gdal
import urllib2, zipfile

if "GISBASE" not in os.environ:
    print "You must be in GRASS GIS to run this program."
    sys.exit(1)

def parse_command_line():
    '''
    Parse command line
    THere are two possible arguments: -d (download dem) and -c (alternate location for config file)
    As well as the usual -h for help message
    Returns a dictionary of the arguments
    '''
    parser = argparse.ArgumentParser(description="Prepare a high resolution NetCDF file for use in WRF-Hydro")
    parser.add_argument("-d","--download-dem",help="Download DEM tiles from HydroSHEDS website", action="store_true")
    parser.add_argument("-c","--config-file",help="Alternate configuration file location (full path and file name)")
    args = parser.parse_args()
    return vars(args)


def load_configs(conf_file):
    ''' 
    Read and parse conf file from same directory as script, 
    or alternate location specified on command line (-c option)
    Returns two dictionaries: 1) directory paths and 2)input,output names and other values
    '''
    dir_dict={}
    default_dict={}
    config = ConfigParser.SafeConfigParser()
    config.readfp(open(conf_file))
    for opt in config.options('Directories'):
        v = config.get('Directories',opt)
        dir_dict[opt] = v

    for opt in config.options('Default'):
        if (opt == 'agg_factor' or opt == 'basin_threshold'):
            v = config.getint('Default', opt)
        else
            v = config.get('default', opt)

        default_dict[opt] = v

    return dir_dict,default_dict



def make_directories(dir_dict):
    '''
    Move into work directory,
    Create the output directories under the work directory
    If work_dir contains a full path, leave it 
    otherwise append the work_dir to user's home directory
    Returns true unless any make dir fails
    '''
    pth = os.path.dirname(dir_dict['work_dir'])
    if not pth:
        pth = os.path.expanduser('~')

    for k,d in dir_dict.iteritems(): 
        new_path = os.path.join(pth,d)
        if not os.path.exists(new_path):
            try:
                os.mkdirs(new_path)
            except OSError, e:
                raise e
                return false

    return True


def get_geo_corners(geo_em):
    '''
    Use netCDF4 library to get corner_lats and corner_lons from geo_em.d03 netcdf file
    Find the minimum and maximum long and lat values in 5 degree units 
    to cover the whole geo_em.d03.nc region.  
    Use all outer corners to find region, and expand to nearest 5 degress
    Return the lower left corner, the cellsize,
    and list of pairs of long/lat 5 degree tiles that covers region
    '''
    nc = netCDF4.Dataset(geo_em, 'r')
    corner_lats = getattr(nc,'corner_lats')
    corner_lons = getattr(nc,'corner_lons')
    cellsize = [getattr(nc,'DX'), getattr(nc,'DY')]
    tile_list = []
    # The lower left corner is the first value in each list of corners
    ll_corner = [ corner_lons[0], corner_lats[0] ]

    # Get the min and max long and lat
    max_ln = max(corner_lons)
    min_ln = min(corner_lons)
    max_lt = max(corner_lats)
    min_lt = min(corner_lats)
    # Round min/max lats and min/max longs down and up to nearest 5 degrees
    tile_max_ln = int(math.ceil(max_ln/5))*5
    tile_min_ln = int(math.floor(min_ln/5))*5
    tile_max_lt = int(math.ceil(max_lt/5))*5
    tile_min_lt = int(math.floor(min_lt/5))*5

    # create list
    for tile_lon in range(tile_min_ln, tile_max_ln, 5):
        for tile_lat in range(tile_min_lt, tile_max_lt, 5):
            tile_list.append([tile_lon, tile_lat])

    return ll_corner, tile_list, cellsize


def get_hydrosheds_tilename(t):
    """
    Use the long/lat pair to determine full name of file to download
    Including the continent abbreviation
    return a filename as string and continent subdir 
    """
    file_ext = "_con_grid.zip"
    #Are tile coords north or south, east or west?
    if t[1]<0:
        lat_prefix="s"
    else:
        lat_prefix="n"
    if t[0]<0:
        lon_prefix="w"
    else:
        lon_prefix="e"
        
    # Longitude values must be formatted with 3 places
    # Use abs() to return absolute values for neg coordinates
    req_tile = ("%s%s%%s" % (lat_prefix, abs(t[1]), lon_prefix, "{0:0>3}".format(abs(t[0))))
    tile_name = req_tile + file_ext

    # Now Find the continent:
    if t[0]>=55:                                # Asia
        continent_subdir = "AS/"
    if (t[0]<=55 and t[0]>-10 and t[1]>=10):    # Europe
        continent_subdir = "EU/"
    if (t[0]<=35 and t[1]<=50 and t[0]>=-10):   # Africa
        continent_subdir = "AF/"
    if (t[0]<-50 and t[1]>=20):                 # North America
        continent_subdir = "NA/"
    if (t[0]<-50 and t[1]<=10):                 # South America
        continent_subdir = "SA/"
    else:
        grass.message("Tiles not found, please download maually")

    return continent_subdir, tile_name



def get_hydrosheds(tile_list,hydrosheds_dir):
    '''
    Use the tile_list to download dem tiles from Hydrosheds website:
    http://earlywarning.usgs.gov/hydrosheds/dataavail.php
    The tile_list variable contains a list of pairs of long/lat
    '''
    HS_baseURL = "http://earlywarning.usgs.gov/hydrodata/sa_con_3s_grid/"
    for t in tile_list:
        continent_subdir, tile_name = get_hydrosheds_tilename(t)
        requrl = HS_baseURL + continent_subdir + tile_name
        try: 
            f = urllib2.urlopen(req_url)
            f_out = open(os.path.join(hydrosheds_dir,tile_name), 'wb')
            msg = "Downloading: %s" % tile_name
            grass.message(msg)
            f_out.write(f.read())
            f_out.close()
        except HTTPError, e:
            print "HTTP Error:", e.code, req_url
            return False
        except URLError, e:
            print "URL error:", e.reason, req_url
            return False

    for z in os.listdir(hydrosheds_dir):
        zf = zipfile.ZipFile(os.path.join(hydrosheds_dir, z), 'r')
        for zi in zf.infolist():
            msg = "Unzipping: %s. Uncompressed size: %s" % (zi.filename, zi.file_size)
            grass.message(msg)
            zf.extract(zi, hydrosheds_dir)
        
    return True



def get_land_lakes(hydrosheds_dir):
    '''
    Download land and lakes shapefiles from GHSSG website:
    http://www.soest.hawaii.edu/pwessel/gshhg/gshhg-shp-2.2.4.zip
    Use to mask out ocean and lakes from the hydrosheds DEM
    '''

    gshhg_URL   = 'http://www.soest.hawaii.edu/pwessel/gshhg/gshhg-shp-2.2.4.zip'
    gshhg_zip       = 'gshhg-shp-2.2.4.zip'  
    gshhg_path   = os.path.join(hydrosheds_dir, gshhg_zip)
    try:
        f = urllib2.urlopen(gshhg_URL)
        f_out = open(gsshg_path, 'wb')
        msg = "Downloading: %s" % gsshg_zip
        grass.message(msg)
        f_out.write(f.read())
        f_out.close()
    except HTTPError, e:
        print "HTTP Error:", e.code, gshhg_URL
        return False
    except URLError, e:
        print "URL error:", e.reason, gshhg_URL
        return False

    zf = zipfile.ZipFile(gsshg_path, 'r')
    for zi in zf.infolist():
        msg = "Unzipping: %s Uncompressed size: %s" % (zi.filename, zi.file_size)
        grass.message(msg)
        zf.extract(zi, hydrosheds_dir)

    return True


def load_data(ll_corner):
    """
    Load into GRASS hydrosheds tiles, lakes and land shapefiles,
    the stations (from csv), the llcorner point ,
    Change header in geo_em_hgt.asc AAIGrid file, and import
    """
    global configs
    ll_coords = "%s|%s" % (llcorner[0], llcorner[1])
    grass.write_command('v.in.ascii', overwrite=True, output=configs['llcorner_vect'], stdin=ll_coords)
    cols="stat_num integer, stat_name text, longitude double precision, latitude double precision"
    grass.run_command('v.in.ascii', overwrite=True, output=configs['ppoints_vect'], input=configs['stations_csv'], separator=",", columns=cols, x=3, y=4 )
    
    # Import Hydrosheds dems
    adf = "w001001.adf"
    hs_dir = configs['hydrosheds_dir']
    for d in os.listdirs(hs_dir):
        if os.path.isfile(os.path.join(hs_dir,d,d,adf):
            in_adf = os.path.join(hs_dir, d, d, adf)
            grass.run_command('r.in.gdal', input=in_adf, output=d, overwrite=True)

    # patch tiles together (first set current region to all tiles
    hs_tiles = grass.mlist_grouped('rast', pattern="*_con")[configs['mapset']]
    grass.run_command('g.region',flags='p', rast=hs_tiles )
    msg = "Patching tiles"
    grass.message(msg)
    grass.run_command('r.patch', input=hs_tiles, output='hydrosheds_raw', overwrite=True)
    grass.run_command('g.mremove', flags='f', rast=hs_tiles)

    # Import GSHHG vectors
    gshhs_dir = "GSHHS_shp"
    # The 'h' subdir has "hi-resolution" shapefiles
    gshhs_path = os.path.join(hs_dir, gshhs_dir,'h')
    # Get two layers: L1 are the shorelines, and L2 the lakes
    shps = ['GSHHS_h_L1.shp','GSHHS_h_L2.shp']
    land_path = os.path.join(gshhs_path, shps[0])
    lakes_path = os.pathjoin(gshhs_path, shps[1])
    grass.run_command('v.in.ogr', dsn=land_path, output='continents', snap=0.001, min_area=10, overwrite=True )
    grass.run_command('v.in.ogr', dsn=lakes_path, output='lakes', snap=0.01, overwrite=True )
    # Use overlay to cut lakes from land areas, then convert to raster
    # Use the raster as a mask to cut out oceans and lakes from the dem
    grass.run_command('v.overlay', flags='t', overwrite=True, ainput='continents', binput='lakes', out='land', operator=not)
    grass.run_command('v.to.rast', input='land', output='land_mask', use=val, val=1)
    grass.run_command('r.mask', raster='land_mask')
    expr = "hydrosheds_dem = hydrosheds_raw" 
    grass.message("Creating masked DEM")
    p = grass.mapcalc(expr)
    p.wait()
    grass.run_command('r.mask', flags="r", raster='land_mask')

    return True


def convert_to_lcc():
    '''
    Switch GRASS to LCC Location, and project layers point to this CRS:
    llcorner, stations
    Set region to dem (from WGS84 Locations) and then project dem into LCC Location.
    '''
    global configs
    map = configs['mapset']
    lccloc = config['lcc_location']
    wgsloc = config['wgs_location']
    llcorner = configs['llcorner_vect']
    stations = configs['ppoints_vect']
    ascii_dir = configs['ascii_dir']
    grass.run_command('g.mapset', mapset=map, location=loc)
    # ReProject llcorner vector point, and station locations to this LOCATION
    grass.run_command('v.proj', input=llcorner, location=wgsloc, mapset=map)
    grass.run_command('v.proj', input=stations, location=wgsloc, mapset=map)
    # Get the new X-Y coords of llcorner
    vinfo = grass.parse_command('v.info', flags="g", map=llcorner)
    x_coord = vinfo['west']
    y_coord = vinfo['north']
    res = configs['rast_resolution']
    agg = configs['agg_factor']
    new_cellsize = res*agg
    # Convert geo_em.d03.nc to AAIGrid,
    # Replace values in header of the file, and import 
    geo_em = configs['geo_em']
    geo_netcdf = "NETCDF:%s:HGT_M" %s geo_em
    geo_em_base = os.path.splitext(os.path.basename(geo_em)[0]
    geo_em_asc = os.path.join(ascii_dir, geo_em_base+'.asc')
    os.system("gdal_translate -of AAIGrid -a_nodata -9999 %s %s" % (geo_netcdf, geo_em_asc) 
    
    return True

def convert_geo_aaigrid(geo_em, asc_dir, llcorner, cellsize, agg_factor)
    """
    Use GDAL to convert geo_em.d03.nc HGT variable to AAIGrid format
    Replace the xllcorner and yllcorner values, as well as the cellsize in the AAIGrid header
    Now import the HGT variable into GRASS (in the LCC Location) and set region to this raster
    Also set resoution to cellsize/agg_factor
    """
    return True


def run_watershed():
    '''
    Perform watershed analysis
    Do reclass of flow direction to match ARC directions
    run r.stream.order and r.stream.snap and convert snapped streams back to raster as frxst_pts
    run r.stream.basins
    '''
    return True


def convert_to_gtiff():
    '''
    Convert each of the watershed rasters to GeoTiff
    '''
    return True



def convert_to_wgs84():
    '''
    Return to WGS84 Location and re-project the stations vector.
    Add Long/lat columns and update coordinate values
    Export to csv file
    '''
    return True



