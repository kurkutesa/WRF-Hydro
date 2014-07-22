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
    -d|--mask-id  : mask id value to be applied
    -m|--mask-var   : a variable in the netcdf used as a mask. 
    -n|--new-val    : the new value to enter into the output netcdf
    -v|--change-var : the variable in the target netcdf to be changed

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
    print ('\tchange_nc.py -i|--input <input netcdf> -o|--output <output netcdf> -d|--mask-id <mask id> -m|mask-var <variable used as mask')
    print ('\t\t -n|--new-val <new value to apply> -v|--change-var <variable in target netcdf to be altered>')


def get_options(argv):
    """
    Get all command line parameters
    Make sure each is required parameter is passed
    """
    try:
        opts, args = getopt.getopt(argv, 'hi:o:d:m:n:v:', ['help','input=','output=','mask-id=','mask-var=', 'new-val=', 'change-var='])
    except getopt.GetoptError:
        print_syntax("Options error")
        return False

    # Initialize option names to empty strings
    in_nc       = ''
    out_nc      = ''
    #change_tbl  = ''
    mask_id     = ''
    mask_var    = ''
    new_val     = ''
    change_var	= ''
    syntax_msg  = ''
    
    for opt, arg in opts:
        if opt in ('-h','--help'):
            print_syntax(syntax_msg)
            return False
        elif opt in ("-i", "--input"):
            in_nc = arg
        elif opt in ("-o", "--output"):
            out_nc = arg
        elif opt in ("-d", "--mask-id"):
            mask_id = arg
        elif opt in ("-m", "--mask-var"):
            mask_var = arg
        elif opt in ("-n", "--new-val"):
            new_val = arg
        elif opt in ("-v", "--change-var"):
            change_var = arg

    options = {'in_nc':in_nc,'out_nc':out_nc,'mask_id':mask_id,'mask_var':mask_var,'new_val':new_val,'change_var':change_var}

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
        if k == 'mask_id' and len(options[k])==0:
            syntax_msg += "No mask id\n"
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


def change_values(in_file, out_file, mask_id, mask_var, new_val, change_var):
    """
    First do a check on the nc files.
    Then create numpy arrays of the input mask variable, and the output change variable
    Replace values in output nc file 'o' in variable 'ch_var', 
    where the variable 'mask' in input nc 'i' matches values in the dictionary 'dict'
    Take new values from 'dict' for each matching mask value
    """

    try:
        os.path.isfile(in_file)
    except:
        print "Input file not available"
        return False
    
    if not os.path.isfile(out_file):
        print "Copying %s to %s" % (in_file, out_file)
        shutil.copyfile(in_file,out_file)
    else:
        print "Writing to output file: %s" % out_file

    # Open input file for reading, output file for appending
    in_nc = Dataset(in_file, 'r')
    out_nc = Dataset(out_file, 'a')
    in_var = in_nc.variables[mask_var]
    out_var = out_nc.variables[change_var]
    if in_var.dimensions == out_var.dimensions and in_var.shape == out_var.shape:
        # nc files OK, good to go
        # Get shape and number of dimensions
        shp = in_var.shape
        dims = len(shp)
        # create numpy arrays from the variables in each nc file
        # Note: must be indexed: [:]. Otherwise array will hold the object, not values
        in_arr  = np.array(in_var[:])
        out_arr = np.array(out_var[:])
        
        # Loop thru input array with ndenumerate function. 
        for idx, val in np.ndenumerate(in_arr):
            #Check each index if it matches a mask value
            #for m,v in dict.iteritems():
            if (int(float(val)) == int(float(mask_id))):
            # If there is a match, set the output array at this index 
            # to the new value from the mask dictionary
                out_arr[idx] = new_val

        # Now push numpy array back to netcdf variable
        out_var[:] = out_arr[:]
        in_nc.close()
        out_nc.close()
        return True

    else:
        return False


def main(argv):
  options = get_options(argv)
  if (options == False):
    print '\nEnter all options\n'
  else:
    in_nc       = options['in_nc']
    out_nc      = options['out_nc']
    mask_id     = options['mask_id']
    mask_var    = options['mask_var']
    new_val     = options['new_val']
    change_var  = options['change_var']

    #mask_dict = read_mask_values(options['change_tbl'])
    success = change_values(in_nc, out_nc, mask_id, mask_var, new_val, change_var)
    if success:
        print "Completed"
    else:
        print "Change values failed"


if __name__ == "__main__":
  main(sys.argv[1:])
