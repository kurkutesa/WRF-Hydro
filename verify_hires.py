#!/usr/bin/env python
"""
Analyze variables from an input netCDF file
The frxst_pts variable is scanned for values of 0. Each 0 value indicates a drainage point.
When a drain point is found, the values of other variables at the same pixel location 
are extracted: longitude, latitude, elevation, streamorder
All values are saved into an array, and finally exported to the output file
"""

import netCDF4
import numpy as np
import sys,math,os
import argparse

# Command line arguments
parser = argparse.ArgumentParser(description="Analyze gis_hires netCDF file", usage='%(prog)s [options]')
parser.add_argument("-i","--input", dest="in_nc", help="The path/name of the netCDF input file", nargs='?', type=argparse.FileType('r'), required=True)
parser.add_argument("-o", "--output", dest="out_txt", default="drain_pts.txt", help="The path/name for the output text file", nargs='?', type=argparse.FileType('w'))
args = parser.parse_args()
ncfile = args.in_nc.name
outfile = args.out_txt.name

ncpath, ncfname = os.path.split(ncfile)
print ('Using netCDF file: %s \nin directory: %s' % (ncfname, ncpath))
outpath, outfname = os.path.split(outfile)
print ('Writing results to: %s\n' % outfile)

# Open netCDF file
nc = netCDF4.Dataset(ncfile, 'r')
dims = nc.dimensions
print ("N-S dim: %s \t E-W dim: %s" % (len(dims['y']), len(dims['x'])))
print ('---------------------------------------------------------\n')

# Read required variables into numpy arrays
# Use numpy flipud function to get arrays ordered from bottom to top
# So that drain point id's will be the same as WRF-Hydro
fr_arr 	= np.flipud(nc.variables['frxst_pts'])
topo_arr = np.flipud(nc.variables['TOPOGRAPHY'])
str_arr	= np.flipud(nc.variables['STREAMORDER'])
lat_arr	= np.flipud(nc.variables['LATITUDE'])
lon_arr	= np.flipud(nc.variables['LONGITUDE'])
x_arr	= np.flipud(nc.variables['x'])
y_arr	= np.flipud(nc.variables['y'])
fr_cnt	= 0

# Loop thru the frxst_pts array
print('ID\tStream Order\tLongitude\tLatitude\tElevation')
details=[]
for idx, fr_val in np.ndenumerate(fr_arr):
	if (fr_val == 0) :
		fr_cnt += 1
		str_val = str_arr[idx[0], idx[1]]
		lon_val = lon_arr[idx[0], idx[1]]
		lat_val = lat_arr[idx[0], idx[1]]
		topo_val = topo_arr[idx[0], idx[1]]
		print ('%s\t%s\t%s\t%s\t%s' % (fr_cnt, str_val, lon_val, lat_val, topo_val))
		details.append([fr_cnt,str_val,lon_val,lat_val,topo_val])

# Now do the output
out_f = open(outfile, 'w')
out_f.write('ID,Stream Order,Longitude,Latitude,Elevation\n')
for i in range(len(details)):
	out_f.write('%s,%s,%s,%s,%s\n' % (details[i][0], details[i][1],details[i][2],details[i][3],details[i][4]))
out_f.close()		
#print "{0:0>3}".format(tile_max_ln), "{0:0>3}".format(tile_min_ln)
#print "Tile Max/Min longitude, Max/Min latitude: %s, %s, %s, %s" % ("{0:0>3}".format(tile_max_ln), "{0:0>3}".format(tile_min_ln), tile_max_lt, tile_min_lt)
       

