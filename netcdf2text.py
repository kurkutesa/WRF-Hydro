#!/usr/bin/python
#
"""
Description:	Read a set of wrfout netcdf file, extract the RAINNC variable, 
		and X-Y coordinates of each cell into a text file.
Author:		Micha Silver
Date:		1/10/2014
"""
import netCDF4
import numpy as np
import os,csv,argparse,glob

def netcdf_to_text(ncdir,outdir):
	wrfout_pattern = "wrfout_d03_"
	wrfoutlist = glob.glob(os.path.join(ncdir,wrfout_pattern+"*"))
	for ncname in wrfoutlist:
		print ("Working on: %s" % (ncname,))
			
		ncpath = os.path.join(ncdir, ncname)
		ncfile = netCDF4.Dataset(ncpath, 'r')
		lat = ncfile.variables['XLAT'][:]
		lon = ncfile.variables['XLONG'][:]
		rain = ncfile.variables['RAINNC'][:]
		# Each wrfout netCDF variable has 3 dimensions:
		#print ("Dimentions of netCDF variables: %s" % (rain.shape,))
		# Use the 2nd and third to size the outdata array
		ncols, nrows = len(rain[0]), len(rain[0][0])
		#print("Lengths: LAT-%s, LON-%s" % (ncols, nrows))
		# Output data array will have 3 columns(lat, long, precip) 
		# and enough rows for all the data cells in original netCDF
		outdata = np.empty([3,ncols*nrows])
		i = 0
		for y in range(nrows):
		    for x in range(ncols):
			outdata[0][i] = lon[0][x][y]
			outdata[1][i] = lat[0][x][y]
			outdata[2][i] = rain[0][x][y]
			i = i+1
		
		print ("Outdata contains: %s rows" % (i,))
		ncfile.close()
		
		datestr = os.path.basename(ncname)[11:24]
		outname = "precip_csv_"+datestr+".txt"	
		print ("Saving to output file: %s\n" % (outname,))	
		outpath = os.path.join(outdir, outname)
		csvfile = open(outpath, "w")
		writer = csv.writer(csvfile)
		for r in range(ncols*nrows):
			writer.writerows( [(outdata[0][r], outdata[1][r], outdata[2][r])] )

		csvfile.close()


# Main work starts here
parser = argparse.ArgumentParser("Get command line arguments")
parser.add_argument("-i", "--wrfdir", default=".", required=True, help="Directory of wrfout netCDF files") 
parser.add_argument("-o", "--outdir", default=".", help="Directory to store output csv")
# Get arguments
args = parser.parse_args()
# Run the function
netcdf_to_text(args.wrfdir, args.outdir)

