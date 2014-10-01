#!/usr/bin/python
#
"""
Description:	Read a set of wrfout netcdf file, extract the RAINNC variable, 
		and X-Y coordinates of each cell into a text file.
Author:		Micha Silver
Date:		1/10/2014
"""
import netCDF4
import os,csv,argparse

def parse_netcdf(ncname,ncdir,outdir):

	ncpath = os.path.join(ncdir,ncname)	
	ncfile = netCDF4.Dataset(ncpath, 'r')
	lat = ncfile.variables['XLAT'][:]
	lon = ncfile.variables['XLONG'][:]
	rain = ncfile.variables['RAINNC'][:]

	nlat, nlon = len(lat), len(lon)
	datestr = ncname[11:24]
	outname = "precip_"+datestr+".txt"
	outdata = []

	for y in range(nlat):
	    for x in range(nlon):
		outdata.append((x,y,rain[x,y]))

	ncfile.close()
	
	outpath = os.path.join(outdir, outname)
	csvfile = open(outpath, "w")
	writer = csv.writer(csvfile)
	for row in outdata:
		writer.writerows("%s,%s,%s" % (row[0], row[1], row[2]) )

	csvfile.close()


# Main work starts here
parser = argparse.ArgumentParser("Get command line arguments")
parser.add_argument("-n", "--ncfile", required=True, help="wrfout netCDF file")
parser.add_argument("-i", "--indir", default=".", help="Directory of wrfout netCDF files") 
parser.add_argument("-o", "--outdir", default=".", help="Directory to store output csv")

args = parser.parse_args()
parse_netcdf(args.ncfile, args.indir, args.outdir)



# Using ImageMagick convert:
# http://blog.room208.org/post/48793543478
# $ convert -fuzz 1% -delay 1x8 `seq -f %03g.png 10 3 72` \
#                  -coalesce -layers OptimizeTransparency animation.gif
