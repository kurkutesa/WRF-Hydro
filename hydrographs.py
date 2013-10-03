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
import ConfigParser


def probability_period(l):
  """
	Check which level a hydro station is in, and return a string 
	to put into the graph title
  
  """
  prob_reply=""

  if ((l is None) | (l == -1)):
    prob_reply=" (No probability data)"
  elif l==0:
    prob_reply=" No flow"
  elif l==1:
    prob_reply=" less than 2 years"
  elif l==2:
    prob_reply=" 2 to 5 years"
  elif l==3:
    prob_reply=" 5 to 10 years"
  elif l==4:
    prob_reply=" 10 to 25 years"
  elif l==5:
    prob_reply=" 25 to 50 years"
  elif l==6:
    prob_reply=" 50 to 100 years"
  else :
    prob_reply=" greater than 100 years"

  return prob_reply


def get_stationid_list():
  """
  Make a postgresql database connection and query for a list of all station ids
  Get both the hydro_station ids and the drain_point ids
  return the list
  """
  # First get configurations
  config = ConfigParser.ConfigParser()
  config.read("hydrographs.conf")
  h = config.get("Db","host")
  db = config.get("Db","dbname")
  u = config.get("Db","user")
  pw = config.get("Db","password")

  conn_string = "host='"+h+"' dbname='"+db+"' user='"+u+"' password='"+pw+"'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    sql = "SELECT id FROM hydro_stations WHERE active='t' UNION SELECT id FROM drain_points WHERE active='t'"
    curs.execute(sql)
    rows = curs.fetchall()
    return rows
  except psycopg2.DatabaseError, e:
    print 'Error %s' % e    
    sys.exit(1)		  
  finally:
    if conn:
      conn.close()


def get_station_num(id):
  """
  Make a postgresql database connection and get the station_num 
  from the hydrograph view for a given station id
  return the number
  """
  # First get configurations
  config = ConfigParser.ConfigParser()
  config.read("hydrographs.conf")
  h = config.get("Db","host")
  db = config.get("Db","dbname")
  u = config.get("Db","user")
  pw = config.get("Db","password")

  conn_string = "host='"+h+"' dbname='"+db+"' user='"+u+"' password='"+pw+"'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    sql = "SELECT station_num FROM hydrograph_locations WHERE id= %s;" % id
    curs.execute(sql)
    row = curs.fetchone()
    if (curs.rowcount <1):
      return None
    else:
      return row[0]
  except psycopg2.DatabaseError, e:
    print 'Error %s' % e    
    sys.exit(1)		  
  finally:
    if conn:
      conn.close()



def update_maxflow(id, mf):
  # First get configurations
  config = ConfigParser.ConfigParser()
  config.read("hydrographs.conf")
  h = config.get("Db", "host")
  db = config.get("Db","dbname")
  u = config.get("Db", "user")
  pw = config.get("Db", "password")
  conn_string = "host='"+h+"' dbname='"+db+"' user='"+u+"' password='"+pw+"'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    sql = "UPDATE max_flows SET max_flow=%s WHERE id=%s;" % (mf, id)
    #print "Executing: "+sql
    curs.execute(sql)
    conn.commit()
  except psycopg2.DatabaseError, e:
    print 'Error %s' %e
    sys.exit(1)

  # After update the flow level has been set in the db table (by a trigger)
  # Query for and return the flow level value
  try:
    curs.execute("SELECT flow_level FROM max_flows WHERE id = %s" % id)
    row = curs.fetchone()
    cnt = curs.rowcount
    if (cnt == 1):
      l = row[0]
    else:
      l = None
  except psycopg2.DatabaseError,e:
    print 'Error %s' % e
  finally:
    if conn:
      conn.close()
  return l



def create_graph(prob, num, disch, hrs):
  """ 
  Creates a hydrograph (png image file) using the array of discharges from the input parameter
  The max parameter is used to determine which return period this event is in
  First the function

  """
  # First get configurations
  config = ConfigParser.ConfigParser()
  config.read("hydrographs.conf")
  out_path = config.get("Graphs","out_path")
  out_pref = config.get("Graphs", "out_pref")

  # Make sure target directory exists
  try:
    os.makedirs(out_path)
  except OSError:
    if os.path.exists(out_path):
      pass
    else:
      raise
    
  print "Creating graph for station num: "+str(num)
  fig = plt.figure()
  plt.xlabel('Hours')
  plt.ylabel('Discharge (m3/sec)')
  stnum=str(num)
  plt.suptitle('Station Number: '+ stnum, fontsize=18)
  prob_str="Return period: "+prob
  plt.title(prob_str,size=14)
  ln = plt.plot(hrs, disch)
  plt.ylim(ymin=0)
  plt.setp(ln, linewidth=2, color='b')
  outpng=os.path.join(out_path,out_pref + stnum + ".png")
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

  # First get configurations
  config = ConfigParser.ConfigParser()
  config.read("hydrographs.conf")
  min_hr = config.getint("General", "min_hr")
  max_hr = config.getint("General","max_hr")
  hr_col = config.getint("General", "hr_col")
  in_path = config.get("General", "in_path")
  disch_col = config.getint("General", "disch_col")

  input_file = os.path.join(in_path, sys.argv[1])
  # Get the list of station ids
  ids = get_stationid_list()

  with open(input_file, 'rb') as f:
    data_rows = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
    # config parameters:
    for i in range(0,len(ids)):
      id = ids[i][0]
      print "Working on station id: "+str(id)
      datai = []
      for row in data_rows:
			# THe third column (numbered from 0) has the station id
      # Collect all data for one station into a data array
        if (int(row[3]) == id):
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
          # Get hour and discharge column from config
          hr = int(datai[j][hr_col])/3600

          # Limit graph from minimum hour (from config) to max hour 
          if (hr>min_hr and hr<=max_hr):
            hrs.append(hr)
	          # Get "disch_col" column: has the discharge in cubic meters
            dis = round(float(datai[j][disch_col]))
            disch.append(dis)
            # Keep track of the maximum discharge for this hydro station
            if dis>max_disch:
	  			    max_disch=dis

				# Now use the max_disch to update the maxflows database table
				# and get back the flow_level for this station
        level = update_maxflow(int(id), int(max_disch))

        print "Using: "+str(len(hrs))+" data points."
     	  #	print "Hour: " + str(hr) + "Disch: " + str(dis)
        # Continue ONLY if level actually has value
        if (level is None):
          print "No station with id: "+str(id)
          exit
        else:
          station_num = get_station_num(int(id))
          print "Station num: "+str(station_num)+" has max discharge: "+str(max_disch)
          # Find which return period this max flow is in
          prob_str = probability_period(level) 
          # Create the graph
          create_graph(prob_str, station_num, disch, hrs)

      f.seek(0)


if __name__ == "__main__":
	main()
