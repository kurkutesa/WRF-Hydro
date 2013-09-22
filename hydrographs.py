#!/usr/bin/env python
"""
  This routine reads a CSV file of flow rates for each of the hydrometer stations
  with hourly data for a period of 24 hours.
  All discharge values are entered into an array for each hydrostation
  The array of discharge values is used build a hydrometric graph for each station
  Graphs are output to png files, one for each station
"""

import matplotlib.pyplot as plt
import numpy as np
import os, csv, sys
import psycopg2


def probability_period(max, prob_array):
  """
  Find the probability of a maximum flow rate (return period) for a hydro station
  Takes the max flow rate, and array of probability values
  Finds which range of probabilities this max falls in.
  The array of probabilities contains 5 values:
  5 yr event, 10 yr event, 25 year event, 50 year event, 100 yr event  

  Returns a string
  
  """

  prob_reply=""

  # Handle the case of no values in prob_array
  if ((prob_array[0] is None) | (prob_array[0]==0)):
    prob_reply=" (No return period data)"
  elif max <= prob_array[0]:
    prob_reply=" less than 5 years"
  elif max <= prob_array[1]:
    prob_reply=" 5 to 10 years"
  elif max <= prob_array[2]:
    prob_reply=" 10 to 25 years"
  elif max <= prob_array[3]:
    prob_reply=" 25 to 50 years"
  elif max <= prob_array[4]:
    prob_reply=" 50 to 100 years"
  else :
    prob_reply=" greater than 100 years"

  return prob_reply


def hydrometer_probs():
  """
	Make a postgresql database connection and query for 7 columns:
	the station id, station number and the 5 columns of flow rates for 5 return periods - 
	5 year, 10 year, 25 year, 50 year and 100 year

	Returns an array

  """

  conn_string = "host='maps.arava.co.il' dbname='ihs' user='ihsdba' password='grby~2013'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    curs.execute("SELECT id, station_num, flow_5yr, flow_10yr, flow_25yr, flow_50yr, flow_100yr FROM hydro_stations;")
    rows = curs.fetchall()
    numrows = curs.rowcount
    print "Found: "+str(numrows)+" rows"
    return rows
  except psycopg2.DatabaseError, e:
    print 'Error %s' % e    
    sys.exit(1)		  
  finally:
    if conn:
      conn.close()


def create_graph(prob, num, disch, hrs):
  """ 
  Creates a hydrograph (png image file) using the array of discharges from the input parameter
  The max parameter is used to determine which return period this event is in
  First the function

  """
  print "Creating graph for station num: "+str(num)
  fig = plt.figure()
  plt.xlabel('Hours')
  plt.ylabel('Discharge')
  stnum=str(num)
  plt.suptitle('Station Number: '+ stnum, fontsize=18)
  prob_str="Return period: "+prob
  plt.title(prob_str,size=14)
  ln = plt.plot(hrs, disch)
  plt.setp(ln, linewidth=2, color='b')
  outpng=os.path.join('graphs',"hg_"+ stnum + ".png")
  plt.savefig(outpng)


def main():
  """
  Loops thru a (hard coded) number of index values, and reads rows 
  from the csv file passed on the command line
  Each row contains data for a certain station at a certain time
  The loop aggregates the data, and creates a discharge array for each station
  Then 2 subroutines are called:
  - first to get the probability string for the max flow of each station for this event
  - second to create a hydrograph for this station

  """

  if len(sys.argv) < 2:
    print "Syntax: "+ sys.argv[0] + " <input file>"
    exit

  input_file = sys.argv[1]

  # First get the probabilty parameters for all hydro_stations
  probs_array = hydrometer_probs()
  
  with open(input_file, 'rb') as f:
    data_rows = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
    for i in range(0,120,1):
      print "Working on station id: "+str(i)
      datai = []
      for row in data_rows:
			# THe third column (numbered from 0) has the station id
      # Collect all data for one station into a data array
        if (row[3] == str(i)):
          datai.append(row)

      # Initialize and fill arrays for hours and discharge
      hrs=[]
      disch=[]
      max_disch=0
      if (len(datai) == 0):
        exit
      else:  
        for j in range(len(datai)):
          #	hr = datai[j][2].split(':')[0]
          hr = int(datai[j][0])/3600
          # Limit graph from hour 6:00 to hour 48
          if (hr>6 and hr<=48):
            hrs.append(hr)
	          # The sixth column has the discharge in cubic meters
            dis = round(float(datai[j][6]))
            disch.append(dis)
            # Keep track of the maximum discharge for this hydro station
            if dis>max_disch:
	  			    max_disch=dis

        print "Using: "+str(len(hrs))+" data points."
     	  #	print "Hour: " + str(hr) + "Disch: " + str(dis)
        # Get the probability array for this station
        prob_array=[]*6
        for row in probs_array:
          # Find the row in probs array with the station id for this loop
          # The first item in the row (from 0) contains the station id
          # Slice last 6 items from row (not including station id)
          if row[0]==i:
            prob_array = row[1:]

        # Continue ONLY if the prob_array actually has values
        if (len(prob_array) == 0):
          print "No station with id: "+str(i)
          exit
        else:
          station_num = prob_array[0]
          print "Station num: "+str(station_num)+" has max discharge: "+str(max_disch)
          # Find which return period this max flow is in
          # Slice out only the last 5 items in the prob_array (not including station number)
          prob_str = probability_period(max_disch, prob_array[1:]) 
          # Create the graph
          create_graph(prob_str, station_num, disch, hrs)

        f.seek(0)


if __name__ == "__main__":
	main()
