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
  -c|--change-tbl : table (csv format) of mask id values and new values to be applied
  -m|--mask-var   : a variable in the netcdf used as a mask. 
	-v|--change-var	: the variable in the target netcdf to be changed

  Only those grid cells for which the variable --mask-var contains the value in the change-tbl 
  are used to apply the change. 
  THose cells covered by the mask will have their variable --change-var 
  altered to the value obtained from the change-tbl
"""

import os, getopt, sys, csv
import shutil
import numpy as np
from netCDF4 import Dataset


def print_syntax(m):
    print m
    print ('Syntax: \n\tchange_nc.py -h|--help (this message)')
    print ('\tchange_nc.py -i|--input <input netcdf> -o|--output <output netcdf> -c|--change-tbl <table of ids and new values>')
    print ('\t\t-v|--change-var <variable in target netcdf to be altered> -m|--mask-var <variable used as mask>')


def get_options(argv):
    """
    Get all command line parameters
    Make sure each is required parameter is passed
    """
    try:
        opts, args = getopt.getopt(argv, 'hi:o:c:m:v:', ['help','input=','output=','change-tbl=','change-var=','mask-var='])
    except getopt.GetoptError:
        print_syntax("Options error")
        return False

    # Initialize option names to empty strings
    in_nc       = ''
    out_nc      = ''
    change_tbl  = ''
    change_var	= ''
    mask_var    = ''
    syntax_msg  = ''
    
    for opt, arg in opts:
        if opt in ('-h','--help'):
            print_syntax(syntax_msg)
            return False
        elif opt in ("-i", "--input"):
            in_nc = arg
        elif opt in ("-o", "--output"):
            out_nc = arg
        elif opt in ("-c", "--change-tbl"):
            change_tbl = arg
        elif opt in ("-v", "--change-var"):
            change_var = arg
        elif opt in ("-m", "--mask-var"):
            mask_var = arg

    options = {'in_nc':in_nc,'out_nc':out_nc,'change_tbl':change_tbl, 'change_var': change_var, 'mask_var':mask_var}

    # Make sure all options passed on command line
    have_options = True
    for k, v in options.iteritems():
        if len(v) == 0:
            have_options = False
        if k == 'in_nc' and len(options[k])==0:
            syntax_msg += "No input nc file\n"
            have_options = False
        if k == 'out_nc' and len(options[k])==0:
            syntax_msg += "No output nc file\n"
            have_options = False
        if k == 'change_tbl' and len(options[k])==0:
            syntax_msg += "No mask table file\n"
            have_options = False
        if k == 'change_var' and len(options[k])==0:
            syntax_msg += "No change variable\n"
            have_options = False
        if k == 'mask_var' and len(options[k])==0:
            syntax_msg += "No mask variable\n"
            have_options = False
  
    if (have_options == True):
        return options
    else:
        print_syntax(syntax_msg)
        return False



def read_mask_values(change_tbl):
  """
  Reads the CSV file change_tbl, skipping comment lines (beginning with #)
  collects mask values into a list, indexed by the mask ids
  """
  try:
    f = open(change_tbl, 'r')
    mask_csv = csv.reader(f, delimiter=',')
    mask_dict={}
    for ln in mask_csv:
      if not ln[0].startswith('#'):
        mask_dict[ln[0]]=ln[1]
  except IOError, e:
    print ("Changes table file not available"+str(e))
    return False

  # test
  for i,v in mask_dict.iteritems():
    print "Mask id: "+ i + "\t New value: "+mask_dict[i]
  return mask_dict



def check_nc_files(in_file, out_file, mask, ch_var):
    """
    Verify the the input nc file is available.
    If the output nc is not available, create it
    check that the VARIABLEs mask and ch_var exist in input/output files
    """
    try:
        os.path.isfile(in_file)
    except:
        print "Input file not available"
        return False

    if not os.path.isfile(out_file):
        print "Copying %s to %s" % (in_file, out_file)
        shutil.copyfile(in_file,out_file)

    # Open input file for reading, output file for appending
    in_nc = Dataset(in_file, 'r')
    out_nc = Dataset(out_file, 'r')
    in_var = in_nc.variables[mask]
    out_var = out_nc.variables[ch_var]
    if in_var.dimensions == out_var.dimensions and in_var.shape == out_var.shape:
        return True

    return False


def change_values(i, o, ch_var, mask, dict):
    """
    Replace values in nc file 'o' in variable 'var', 
    where the variable 'mask' in input nc 'i' matches values in the dictionary 'dict'
    Take new values from 'dict' for each matching mask value
    """
    in_nc = Dataset(i, 'r')
    out_nc = Dataset(o, 'a')
    in_var = in_nc.variables[mask]
    out_var = out_nc.variables[ch_var]

    for m,v in dict.iteritems():
        print ("Replace value where mask=%s. \tNew value=%s" % (m, v))



def main(argv):
  options = get_options(argv)
  if (options == False):
    print '\nEnter all options\n'
  else:
    #print 'Options entered:'
    #for k in options:
    #  print '\t'+k+' = '+options[k]
    in_nc       = options['in_nc']
    out_nc      = options['out_nc']
    change_var  = options['change_var']
    mask_var    = options['mask_var']

    print "Altering variable: "+ change_var + "\t Changing output netcdf: "+ out_nc
    mask_dict = read_mask_values(options['change_tbl'])

    # check input and output nc files
    if not (check_nc_files(options['in_nc'],options['out_nc'],options['mask_var'], options['change_var'])):
      print "Netcdf files not available"
      sys.exit(0)
    else:
    # Files check out. Good to go
      print "Proceeding with variable replacement"
      change_values(in_nc, out_nc, change_var, mask_var, mask_dict)

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
