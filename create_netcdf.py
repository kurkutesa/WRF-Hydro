#!/usr/bin/env python

"""
# script: create_netcdf.py
# author: Thomas Rummler

## Change log ##
# modified: Erick Fredj
# Date: Thu Sep  6 13:44:48 IDT 2012

# Modified: Micha
# Thu Jan  2 00:41:54 IST 2014
# Changed paths for input and output
# changed add_factor to 100 (ASTER DEM tiles at 30m resolution) 

# Sat Jan  4 10:15:27 IST 2014
# Returned the agg_factor to 30:
# I created the AAIGrids in ITM, at a resolution of 100m to match the original
# So the relation between the WRF grid (3000 m) and the gis layers (100m) is 30

# Sat Jan  4 17:29:21 IST 2014
# Commented out lines 261-263 
# variable "reduce_to_basin" is not declared anywhere

# Fri Jan 10 23:32:18 IST 2014
# agg_factor set to 30
# We now have ascii grids in LCC projection at resolution 100 m,

# Sat Jan 11 11:52:36 IST 2014
# Added creation of basn_mask NetCDF varialbe like the others

# Sat Jan 11 20:23:13 IST 2014
# Changed the get_hires_dims function: to fix a bug in calulating the nrows * cellsize

# Sat Jan 11 22:06:01 IST 2014
# The resulting NetCDF was shifted to the South because of multiying the Y coordinate by -1
# and then not reversing the matrix. 
# THis is now changed - the "y_coordinate*(-1)" was removed 
# and the np function flipud was re-activated
# in both the read_int_values() and read_float_values() functions
"""

import numpy as np
from netCDF4 import Dataset
from pyproj import Proj


# Aggregation Factor
agg_factor = 30

# Input
asc_dir = '/home/micha/work/IHS/gis_hires/ascii/'
geofile = '/home/micha/work/IHS/gis_hires/NetCDF/geo_em.d03.nc'

# Output
hires_filename = '/home/micha/work/IHS/gis_hires/NetCDF/gis_hires_micha.nc'
basins_txt     = '/home/micha/work/IHS/gis_hires/NetCDF/basins.txt'

def get_hires_dims(filename):

    with open(filename, 'r') as f:
        data = {'ncols':'', 'nrows':'', 'xllcorner':'', 'yllcorner':'', 'cellsize':'', 'NODATA_value':''}
        for i in range(6):
            kk = f.readline()
            var,val = kk.split()
            if var == 'ncols' or var == 'nrows':
                data[var] = int(val)
            else:
                data[var] = float(val.replace(',','.'))
    # Compute coordinates
    x_coordinates = np.arange(
        data["xllcorner"] + (data["cellsize"] / 2.0),
        (data["xllcorner"] + (data["cellsize"] * (data["ncols"] + 1)) - (data["cellsize"]) / 2.0),
        data["cellsize"]\
    )
    # MS: Bug ?? should be from top to bottom? and data["cellsize"]*(data["nrows"]+1)
    y_coordinates = np.arange(
        data["yllcorner"] + (data["cellsize"] / 2.0),
        data["yllcorner"] + (data["cellsize"] * (data["nrows"] + 1)) - (data["cellsize"] / 2.0),
        data["cellsize"]\
    )

    # Sort y coorinates in a descending order
    #y_coordinates = y_coordinates * (-1)

    data['x'] = x_coordinates
    data['y'] = y_coordinates
    data['xgrid'],data['ygrid'] = np.meshgrid(x_coordinates,y_coordinates)
    print 'Calculating coordinates ...'
    data['lons'],data['lats'] = p(data['xgrid'],data['ygrid'],inverse=True)
    return data


def read_asc_int_values(filename):

    with open(filename, 'r') as f:
        data = f.readlines()
    f.close()
    ncols = int(data[0].split()[1])
    nrows = int(data[1].split()[1])
    xllcorner = data[2].split()[1]
    yllcorner = data[3].split()[1]
    cellsize = int(data[4].split()[1])
    NODATA_value = data[5].split()[1]

    values = []

    for i in data[6:]:
        row = i.split()
        for j in row:
            try:
                values.append(int(j))
            except:
                j = round(float(j.replace(',','.')),0)
                values.append(int(j))

    kk = np.asarray(values)
    kk = kk.reshape(nrows,ncols)
    # do not flip, use crappy arcgis output format
    kk = np.flipud(kk)
    del data
    return kk

def read_asc_float_values(filename):

    with open(filename, 'r') as f:
        data = f.readlines()
    f.close()
    ncols = int(data[0].split()[1])
    nrows = int(data[1].split()[1])
    xllcorner = data[2].split()[1]
    yllcorner = data[3].split()[1]
    cellsize = data[4].split()[1]
    NODATA_value = data[5].split()[1]

    values = []

    for i in data[6:]:
        row = i.split()
        for j in row:
            try:
                values.append(float(j))
            except:
                j = float(j.replace(',','.'))
                values.append(j)

    kk = np.asarray(values)
    kk = kk.reshape(nrows,ncols)
    # do not flip, use crappy arcgis output format
    kk = np.flipud(kk)
    del data
    return kk


def agg_basins(hires):
    rows,cols = hires.shape
    lores = np.ma.masked_all((rows/agg_factor,cols/agg_factor),dtype=int)

    for row,rowdata in enumerate(lores):
        print row
        for column, columndata in enumerate(rowdata):

            hires_row_start = row * agg_factor
            hires_column_start = column * agg_factor
            hires_row_end = hires_row_start + agg_factor
            hires_column_end = hires_column_start + agg_factor
            hires_tmp_data = hires[hires_row_start:hires_row_end,hires_column_start:hires_column_end]

            vals = dict()
            for i in hires_tmp_data.flatten():
                if i not in vals:
                    vals[i] = 1
                else:
                    vals[i] += 1

            majority = max(vals, key=vals.get)
            lores[row,column] = majority

    return lores

geo = Dataset(geofile, 'r')

mapproj = geo.getncattr('MAP_PROJ')
stdlon  = geo.getncattr('STAND_LON')
stdlat1 = geo.getncattr('TRUELAT1')
stdlat2 = geo.getncattr('TRUELAT2')
cenlat  = geo.getncattr('CEN_LAT')
cenlon  = geo.getncattr('CEN_LON')

p = Proj(proj='lcc', lon_0=stdlon, lat_0=cenlat, lat_1=stdlat1, lat_2=stdlat2)

hires_specs = get_hires_dims(asc_dir + 'topography.asc')

print "Creating hires file %s ..." %hires_filename

ncfile = Dataset(hires_filename, 'w', format='NETCDF3_64BIT')

ncfile.createDimension('y', size=hires_specs['lats'].shape[0])
ncfile.createDimension('x', size=hires_specs['lons'].shape[1])

ncfile.createVariable('x','f8',('x',),)
ncfile.variables['x'].setncattr('units', 'Meter')
ncfile.variables['x'][:] = hires_specs['x'][:]
ncfile.createVariable('y','f8',('y',),)
ncfile.variables['y'].setncattr('units', 'Meter')
ncfile.variables['y'][:] = hires_specs['y'][:]


ncfile.createVariable('TOPOGRAPHY','f4',('y', 'x',),fill_value=-9999.0)
ncfile.variables['TOPOGRAPHY'].setncattr('coordinates', 'x y')
ncfile.createVariable('LATITUDE','f4',('y', 'x',),fill_value=-9999.0)
ncfile.variables['LATITUDE'].setncattr('coordinates', 'x y')
ncfile.createVariable('LONGITUDE','f4',('y', 'x',),fill_value=-9999.0)
ncfile.variables['LONGITUDE'].setncattr('coordinates', 'x y')
ncfile.createVariable('CHANNELGRID','i2',('y', 'x',),fill_value=-9999)
ncfile.variables['CHANNELGRID'].setncattr('coordinates', 'x y')
ncfile.createVariable('STREAMORDER','i2',('y', 'x',),fill_value=-9999)
ncfile.variables['STREAMORDER'].setncattr('coordinates', 'x y')
ncfile.createVariable('LAKEGRID','i2',('y', 'x',),fill_value=-9999)
ncfile.variables['LAKEGRID'].setncattr('coordinates', 'x y')
ncfile.createVariable('OVROUGHRTFAC','f4',('y', 'x',),fill_value=1)
ncfile.variables['OVROUGHRTFAC'].setncattr('coordinates', 'x y')
ncfile.createVariable('RETDEPRTFAC','f4',('y', 'x',),fill_value=1)
ncfile.variables['RETDEPRTFAC'].setncattr('coordinates', 'x y')
ncfile.createVariable('basn_mask','i2',('y', 'x',),fill_value=-9999)
ncfile.variables['basn_mask'].setncattr('coordinates', 'x y')
ncfile.createVariable('frxst_pts','i2',('y', 'x',),fill_value=-9999)
ncfile.variables['frxst_pts'].setncattr('coordinates', 'x y')
ncfile.createVariable('FLOWDIRECTION','i2',('y', 'x',),fill_value=-9999)
ncfile.variables['FLOWDIRECTION'].setncattr('coordinates', 'x y')

print hires_specs['lats'].min()
print hires_specs['lats'].max()
print hires_specs['lats'].shape

# Fill variables
ncfile.variables['LATITUDE'][:]  = hires_specs['lats'][:]
del hires_specs['lats']

ncfile.variables['LONGITUDE'][:] = hires_specs['lons'][:]
del hires_specs['lons']


print "Reading topography ..."
topography = read_asc_int_values(asc_dir + 'topography.asc')
topography = np.where(topography < -9999, -9999, topography)
ncfile.variables['TOPOGRAPHY'][:]    = topography[:]
del topography

print "Reading flowdirection ..."
flowdirection = read_asc_int_values(asc_dir + 'flowdir.asc')
ncfile.variables['FLOWDIRECTION'][:] = flowdirection[:]
del flowdirection

print "Reading channelgrid ..."
channelgrid = read_asc_int_values(asc_dir + 'channelgrid.asc')
# MS: What is this supposed to be??
#channelgrid = np.where(channelgrid > 0, 0, -9999)
ncfile.variables['CHANNELGRID'][:]   = channelgrid[:]
del channelgrid

print "Reading streamorder ..."
streamorder = read_asc_int_values(asc_dir + 'streamorder.asc')
ncfile.variables['STREAMORDER'][:]   = streamorder[:]
del streamorder

print "Reading basins ..."
basins = read_asc_int_values(asc_dir + 'basins.asc')
# MS: What is this supposed to be??
#channelmask = np.where(basins >= 0, 1, 0)
ncfile.variables['basn_mask'][:]   = basins[:]


print "Reading forecast points ..."
frxst_pts = read_asc_int_values(asc_dir + 'frxstpts.asc')
ncfile.variables['frxst_pts'][:]     = frxst_pts[:]
del frxst_pts

try:
    print "Reading lake grid ..."
    lakegrid = read_asc_int_values(asc_dir + 'lakes.asc')
except:
    lakegrid = None
    pass



"""
if reduce_to_basin == 1:
    channelgrid = np.where(channelmask == 1, channelgrid, -9999)
    streamorder = np.where(channelgrid >= 0, streamorder, -9999)

"""

# MS: What is this supposed to be??
#ncfile.variables['basn_mask'][:]     = -9999

if lakegrid is not None:
    ncfile.variables['LAKEGRID'][:]  = lakegrid[:]

#ncfile.variables['gw_basns'][:] = basn_mask[:]
#print np.where(ncfile.variables['frxst_pts'][:] >= 0)

ncfile.close()

# groundwater basins are defined in a plain text file -->
# --> adapt path for gwbasmskfil in noah_wrfcode.namelist
# not on the hires grid --> wrf grid
# do not flip, use crappy arcgis output format


# if aggfctr > 1: basin mask needs to be aggregated to wrf grid

basins     = agg_basins(basins)
basin_file = open(basins_txt, 'w')

for line in range(basins.shape[0]):
    for j in basins[line,:]:
        basin_file.write(str(j) + '\n')

basin_file.close()


print 'Done!'


