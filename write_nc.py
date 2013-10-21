#log# Automatic Logger file. *** THIS MUST BE THE FIRST LINE ***
#log# DO NOT CHANGE THIS LINE OR THE TWO BELOW
#log# opts = Struct({'__allownew': True, 'logfile': 'write_nc.py'})
#log# args = []
#log# It is safe to make manual edits below here.
#log#-----------------------------------------------------------------------
#_ip.magic("logstart write_nc.py")

import netCDF4 as nc
# Open wrfout for reading, new netcdf for writing
mync = nc.Dataset('mytest.nc', 'w')
wrf = nc.Dataset('wrfout_d03_2013-10-17_000000', 'r')
# Get 'T' variable dimensions and sizes
temp = wrf.variables['T']
print(temp.dimensions)
print(temp.shape)

# Duplicate in new netcdf file
mync.createDimension('time',1)
mync.createDimension('b-t',29)
mync.createDimension('s-n',222)
mync.createDimension('w-e',120)
mync.createVariable('TEMPX2','double',('time','b-t','s-n','w-e'))

# Check new variable
tempx2 = mync.variables['TEMPX2']
print(tempx2.dimensions)
print(tempx2.shape)

# Get values for 'T' variable from wrfout 
# Note: must be indexed: [:]. Otherwise t will hold the object, not values
t = wrf.variables['T'][:]
#print(t)
# put T * 2 into new netcdf file
mync.variables['TEMPX2'][:] = t*2

# Get new values from new netcdf file
# and compare to wrfout values
print("Original values in wrfout")
print(temp[0][1])
print("-------------------------")
print("New values")
print(tempx2[0][1])

mync.close()

#_ip.magic("logoff ")
