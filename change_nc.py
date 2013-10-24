#!/usr/bin/env python
"""
  Author:   Micha Silver
  Version:  0.1

  Description:  
  This routine reads a netcdf file, copies to a new filename
  then alters one variable in the new file, 
  based on parameters passed on the command line

  Command line options:
  -i|--input      : input netcdf filename
  -o|--output     : output netcdf filename
  -c|--change-var : variable name to be changed
  -n|--new-value  : new value to be inserted into the variable
  -m|--mask-var   : a variable in the netcdf used as a mask. 
  -v|--mask-value : the value of the --mask-var to be used as a mask

  Only those grid cells for which the variable --mask-var contains the value --mask-val 
  are used to apply the change. 
  THose cells covered by the mask will have their variable --change-var 
  altered to the value of --new-value

"""

import os, getopt, sys
import scipy.io.netcdf as nc

def print_syntax():
  print ('Syntax: \n\tchange_nc.py -h|--help (this message)')
  print ('\tchange_nc.py -i|--input <input netcdf> -o|--output <output netcdf>')
  print ('\t\t-c|--change-var <variable to be changed> -n|--new-value <new value to be inserted>')
  print ('\t\t-m|--mask-var <variable used as mask> -v|--mask-value <value used as mask>')

def get_options(argv):
  try:
    opts, args = getopt.getopt(argv, 'hi:o:c:n:m:v:', '[help, input=,output=,change-var=,new-value=,mask-var=,mask-value=]')
  except getopt.GetoptError:
    print_syntax()
    return False

# Initialize option names to empty strings
  in_nc =     ''
  out_nc =    ''
  change_var =''
  new_val =   ''
  mask_var =  ''
  mask_value =''

  for opt, arg in opts:
    if opt in ('-h','-help'):
      print_syntax()
      return False
    elif opt in ("-i", "--input"):
      in_nc = arg
    elif opt in ("-o", "--output"):
      out_nc = arg
    elif opt in ("-c", "--change-var"):
      change_var = arg
    elif opt in ("-n", "--new-value"):
      new_val = arg
    elif opt in ("-m", "--mask-var"):
      mask_var = arg
    elif opt in ("-v", "--mask-value"):
      mask_value = arg

  options = {'in_nc':in_nc,'out_nc':out_nc,'change_var':change_var,'new_val':new_val, 'mask_var':mask_var,'mask_value':mask_value}

  # Make sure all options passed on command line
  have_options = True
  for k, v in options.iteritems():
    if len(v) == 0:
      have_options = False
  
  if (have_options == True):
    return options
  else:
    print_syntax()
    return False


def main(argv):
  options = get_options(argv)
  if (options == False):
    print 'Enter all options'
  else:
    print 'Options entered:'
    for k in options:
      print '\t'+k+' = '+options[k]

"""
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
"""

if __name__ == "__main__":
  main(sys.argv[1:])
