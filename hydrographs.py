#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Author:   Micha Silver
Version:  0.2
Description:  
  This routine reads a CSV file of flow rates for each of the hydrometer stations
  with hourly data for a period of 24 hours.
  All discharge values are entered into an array for each hydrostation
  The array of discharge values is used build a hydrometric graph for each station
  Graphs are output to png files, one for each station

Options:
	Command line takes only one option: the directory containing hydrographs.conf (the config file)
	all other configurations are in that file
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
import datetime 
import numpy as np
import os, csv, sys, errno, shutil
import psycopg2
import ConfigParser, logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_alerts():
  """ 
  Send an email to each user, based on the level she requests,
  listing the hydro stations, and the max flow expected at that station
  for stations with flow return rate >= the level the user asks for
  rate = 0 means no alerts
  rate = 1 means send alerts for any flow > 1 cube per sec
  rate = 2 means send alerts for any flow above 2 yr return rate
  rate = 3 means send alerts for any flow above 5 yr return rate
  etc...
  """
  # First get list of users with rate >0
  global host
  global dbname
  global user
  global password
  
  conn_string = "host='"+host+"' dbname='"+dbname+"' user='"+user+"' password='"+password+"'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    sql = "SELECT full_name, email_addr, reshut_num, alert_level, pk_uid FROM users WHERE active='t' and alert_level>0"
    curs.execute(sql)
    users = curs.fetchall()
  except psycopg2.DatabaseError, e:
    logging.error('Error %s',  e)
    sys.exit(1)

  # smtp connection details from conf file
  smtp_user = config.get("SMTP","smtp_user")
  smtp_pass = config.get("SMTP", "smtp_pass")
  smtp_server = config.get("SMTP", "smtp_server")
  smtp_port = config.getint("SMTP", "smtp_port")

  # Loop thru users and get all stations with return period equal or above the user's request
  for u in users:
    #logging.info("Sending alert to User: %s with ID: %s at: %s for return period %s" ,u[0], u[4], u[1], u[3])
    # For each user, find the hydrographs she has access to, 
    # with return rate above her requested level
    sql = 	"SELECT h.station_name, m.max_flow, to_char(m.max_flow_ts,'DD-MM-YYYY HH24:MI') "
    sql += 	" FROM max_flows AS m JOIN hydro_stations AS h ON m.id=h.id "
    sql +=	" WHERE h.reshut_num IN (SELECT reshut_num FROM access WHERE user_id=%s)"
    sql +=	" AND m.flow_level >= %s AND h.active='t';"
    data = (u[4], u[3])
    curs.execute(sql, data)
    stations = curs.fetchall()
    alert_count = curs.rowcount
    if alert_count == 0:
      continue
    
    logging.info ("Found %s stations with alert for user %s ." % (alert_count, str(u[1])))
	
    # Setup smtp connection
    svr = smtplib.SMTP(smtp_server, smtp_port)
    sendfrom = 'micha@arava.co.il'
    rcptto = u[1]
    # Start constructing email message
    fh = open('alert_header.txt','r')
    f = open('alert_msg.txt','r')
    ff= open('alert_footer.txt','r')
    body_text = fh.read()
    body_text += "שלום %s :" % str(u[0])
    body_text += f.read()
    for h in stations:
    #logging.info("ALerting: %s for station: %s. Max Flow: %s",u[0], h[0], h[1])
      body_text += "<tr><td>%s</td><td style=\"text-align:center;\">%s</td><td style=\"text-align:center;\" dir=ltr>%s</td></tr>" % ( str(h[0]), str(h[1]), str(h[2]) )
    
    body_text += ff.read()
    msg = MIMEText(body_text, 'html')
    msg['From'] = sendfrom
    msg['To'] = rcptto
    msg['Subject'] = "WRF-Hydro alert"
    # message is ready, perform the send
    try:
      svr.ehlo()
      svr.starttls()
      svr.ehlo()
      svr.login(smtp_user,smtp_pass)
      svr.sendmail(sendfrom, rcptto, msg.as_string())
    except smtplib.SMTPException, e:
      logging.error("SMTP failed: %s" % str(e))
    finally:
      svr.quit()



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
  global host
  global dbname
  global user
  global password

  conn_string = "host='"+host+"' dbname='"+dbname+"' user='"+user+"' password='"+password+"'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    sql = "SELECT id FROM hydro_stations WHERE active='t' UNION SELECT id FROM drain_points WHERE active='t'"
    curs.execute(sql)
    rows = curs.fetchall()
    return rows
  except psycopg2.DatabaseError, e:
    logging.error('Error %s',  e)		
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
  global host
  global dbname
  global user
  global password

  conn_string = "host='"+host+"' dbname='"+dbname+"' user='"+user+"' password='"+password+"'"
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
    logging.error('Error %s', e)		
    sys.exit(1)			
  finally:
    if conn:
      conn.close()



def update_maxflow(id, mf, mt):
  """
  Update the database table "max_flows" with the maximum flow
  for a station id (passed as parameters)
  Requery to get the flow level value (set by a trigger)
  Return the flow level value
  """
  # First get configurations
  global host
  global dbname
  global user
  global password

  conn_string = "host='"+host+"' dbname='"+dbname+"' user='"+user+"' password='"+password+"'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    sql = "UPDATE max_flows SET max_flow=%s, max_flow_ts=%s WHERE id=%s;"
    data = (mf, mt, id)
    #logging.debug("Executing: "+sql+data)
    curs.execute(sql, data)
    conn.commit()
  except psycopg2.DatabaseError, e:
    logging.error('Error %s',e)
    sys.exit(1)

  # After update the flow level has been set in the db table (by a trigger)
  # Query for and return the flow level value
  try:
    sql = "SELECT flow_level FROM max_flows WHERE id = %s"
    data = (id,)
    curs.execute(sql, data)
    row = curs.fetchone()
    cnt = curs.rowcount
    if (cnt == 1):
      l = row[0]
    else:
      l = None
  
  except psycopg2.DatabaseError,e:
    logging.error('Error %s', e)
  finally:
    if conn:
      conn.close()
	
  return l



def create_graph(prob, num, disch, hrs, dt):
    """ 
    Creates a hydrograph (png image file) using the array of discharges from the input parameter
     """
    global out_path
    global out_pref
    # Make a name for the date-specific target directory
    out_dir = os.path.join(out_path, dt)
    # Make sure target directory exists
    try:
        os.makedirs(out_dir)
    except OSError:
        if os.path.exists(out_dir):
            pass
        else:
            raise

    logging.info("Creating graph for station num: %s",str(num))
    fig = plt.figure()
    plt.xlabel('Hours')
    plt.ylabel('Discharge (m3/sec)')
    stnum=str(num)
    plt.suptitle('Station Number: '+ stnum, fontsize=18)
    prob_str="Return period: "+prob
    plt.title(prob_str,size=14)
    plt.figtext(0.13, 0.87, "Initialized: "+dt, size="medium", weight="bold", backgroundcolor="#EDEA95")
    ln = plt.plot(hrs,disch)
    # Get max discharge to size the graph
    try:
        dis_max = max(disch)
    except:
        dis_max = 0

    if dis_max <= 10:
        y_max = 10
    else:
        y_max = 1.05*dis_max
	
    plt.ylim(ymin=0, ymax=y_max)
    plt.setp(ln, linewidth=3, color='b')
    # Setup date format for X axis
    xfmt = md.DateFormatter('%d-%m-%Y %H:%M')
    plt.gca().xaxis.set_major_formatter(xfmt)
    ax = fig.add_subplot(111)
    ax.xaxis_date() 
    plt.setp(ax.get_xticklabels(), rotation=30, fontsize=7)
    outpng=os.path.join(out_dir,out_pref + stnum + ".png")
    plt.savefig(outpng)



def do_loop(data_rows):
  """
  Loops thru the list of station ids, 
  For each id, search for those lines in data that match that id
  Obtains the discharge and hour values, and accumulates them into lists
  Send those lists to the create graph function
  """
  # Get the list of station ids
  ids = get_stationid_list()
			
  for i in range(0,len(ids)):
    id = ids[i][0]
    logging.info("Working on station id: %s",str(id))
    datai = []
    for row in data_rows:
    # THe third column (numbered from 0) has the station id
    # Collect all data for one station into a data array
      if (int(row[3]) == id):
        datai.append(row)
        
    # Initialize the two arrays for hours and discharge
    hrs=[]
    disch=[]
    dis_times=[]
    max_disch=0
    if (len(datai) == 0):
      logging.warning("No data for id: %s", str(id))
      exit
    else:
      # Grab the date for use later in the graph (needed only once)
      date_str = datai[1][1]
      #logging.debug("Data for date: ",date_str)
      max_disch_time = datai[1][dt_str_col]

      for j in range(len(datai)):
      # Collect the date strings and discharge from this subset of data
      # Get hour and discharge column from config
        hr = (int(datai[j][hr_col]))/3600
        dis_time = matplotlib.dates.datestr2num(datai[j][dt_str_col])
      # Limit graph from minimum hour (from config) to max hour 
      # Never mind this 48 hour check, depend only on the length of the run
      #if (hr>min_hr and hr<=max_hr):
        hrs.append(hr)
        dis_times.append(dis_time)
        # Get "disch_col" column: has the discharge in cubic meters
        dis = float(datai[j][disch_col])
        disch.append(dis)
        # Keep track of the maximum discharge and time for this hydro station
        if dis>max_disch:
          max_disch = dis
          max_disch_time = datai[j][dt_str_col]

      # Now use the max_disch to update the maxflows database table
      # and get back the flow_level for this station
      level = update_maxflow(int(id), max_disch, max_disch_time)

      logging.debug( "Using: %s", str(len(hrs)), " data points.")
      #logging.debug( "Hour: %s", str(hr),  "Disch: %s", str(dis))
      # Continue ONLY if level actually has value
      if (level is None):
        logging.warning( "No station with id: %s",str(id))
        exit
      else:
        station_num = get_station_num(int(id))
        logging.debug( "Station num: %s has max discharge: %s", str(station_num), str(max_disch))
        # Find which return period this max flow is in
        prob_str = probability_period(level) 
        # Create the graph
        create_graph(prob_str, station_num, disch, dis_times, date_str)



def get_latest_datadir():
  """
  Scans the output directory to get timestamps of each
  Finds the directory with a timestamp newer than the timestamp
  stored in the "last_timestamp" file
  Returns the newer data directory
  """
  global in_path
  global ts_file
  global data_file

  # First read existing timestamp from last timestamp file
  try:
    f = open(ts_file,"r+")
    # Convert timestamp to int. We don't care about fractions of seconds
    last_ts = int(float(f.readline()))

  except IOError as e:
  # Can't get a value from the last timesatmp file. Assume 0
    logging.warning( "Can't access timestamp file: %s", e.strerror)
    last_ts = 0
    f = open(ts_file, "w")

  new_ts = None
  new_data_dir = None
  for d in os.listdir(in_path):
    if os.path.isdir(os.path.join(in_path,d)):
      #logging.debug("Trying path: %s", os.path.join(in_path,d))
      try:
        ts = int(os.path.getmtime(os.path.join(in_path,d,data_file)))
        # Compare timestamp for each frxst file in each subdir 
        # with the value from the last timestamp file
        if ts > last_ts:
          new_ts = ts
          # Reset last_ts so that if the directories are not checked in order
          # The most recent timestamp will always be used
          last_ts = ts
          new_data_dir = d
    
      except OSError as e:
        logging.warning("Data file in subdir: %s not yet available. %s", d, e.strerror)

  # If there is no newer frxst file, return None
  # otherwise return the subdir of the new data
  # and write out the new timestamp to the last timestamp file (for next time)
  if new_ts is None:
    logging.info("No new data file")
    f.close()
    return None

  else:
    f.seek(0)
    logging.debug("Updating last_timestamp to: "+str(new_ts))
    f.write(str(new_ts))
    f.truncate()
    f.close()
    logging.info("Using data directory: %s", new_data_dir)
    
  return new_data_dir



def parse_frxst(dirname):
  """
  Scan the input data file, and get all rows into a list of lists
  Add a column "datestr" wihich concatenates the date and hour
  Return the list
  """
  global in_path
  global data_file

  input_file = os.path.join(in_path, dirname, data_file)
  data_rows=[]
  try:
    f = open(input_file, 'rb')
    for line in f.readlines():
      # Force discharge to a float
      secs, dt, hr, id, disch = int(line[0:8]), line[9:19], line[20:28], int(line[32:36]), float(line[59:66])
      dt_str = dt+" "+hr
      atuple=(secs,dt,hr,id,disch,dt_str)
      data_rows.append(atuple)
    
    if (len(data_rows) > 1):
      logging.info("Data file contains %s rows", str(len(data_rows)))
    else:
      logging.error("No rows in data file!")
      return None

  except IOError as e:
    if e.errno == errno.EACCES:
      logging.error("Data file not accessible: %s",e.strerror)
    else:
      logging.error("Data file not available: %s",e.strerror)
    raise
    return None

  f.close
  return data_rows


def upload_flow_data(data_rows):
  """
  Creates a database connection,
  inserts all rows from the data_rows array
  into the db table predicted_flow_data
  """
  # First get configurations
  global host
  global dbname
  global user
  global password

  conn_string = "host='"+host+"' dbname='"+dbname+"' user='"+user+"' password='"+password+"'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    for row in data_rows:
      dt = row[1]+" "+row[2]
      id = row[3]
      mf = row[4]
      data = (dt, id, mf)
      sql = "INSERT INTO model_flow_data (model_timestamp, station_id, max_flow) VALUES (%s, %s, %s)"
      curs.execute(sql,data)

    conn.commit()
    logging.info("Database upload completed")

  except psycopg2.DatabaseError, e:
    logging.error('Error %s', e)
    sys.exit(1)
  finally:
    if conn:
      conn.close()


def upload_model_timing(data_rows):
  """
  Grab the init date-time of the gfc data (from the first row of data_rows)
  and the time the model completed (from the last_timestamp file)
  INSERT a row into the model_timing database table with three timestamps:
  gfc init, wrf completed, and graphs available
  """
  global ts_file
  global host
  global dbname
  global user
  global password

  # Get init hour from the data
  gfc_init = data_rows[1][5]
  # Read existing timestamp from last timestamp file
  try:
    f = open(ts_file,"r+")
    last_ts = float(f.readline())

  except IOError as e:
  # Can't get a value from the last timesatmp file. Assume 0
    logging.warning( "Can't access timestamp file: %s", e.strerror)
    last_ts = 0
  
  f.close()

  model_complete = datetime.datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d %H:%M')
  graphs_complete = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
  #print "GFC: "+str(gfc_init)+", MODEL: "+str(model_complete)+", GRAPHS: "+str(graphs_complete) 

  conn_string = "host='"+host+"' dbname='"+dbname+"' user='"+user+"' password='"+password+"'"
  try:
    conn = psycopg2.connect(conn_string)
    curs = conn.cursor()
    
    data = (str(gfc_init), str(model_complete), str(graphs_complete))
    sql = "INSERT INTO model_timing VALUES (to_timestamp(%s,'YYYY-MM-DD HH24:MI'), "
    sql += "to_timestamp(%s,'YYYY-MM-DD HH24:MI'), to_timestamp(%s,'YYYY-MM-DD HH24:MI'))"
    curs.execute(sql, data)
    conn.commit()

  except psycopg2.DatabaseError, e:
    logging.error('Error %s', e)
    sys.exit(1)
  finally:
    if conn:
      conn.close()

def copy_to_archive(datadir):
  """ 
  Copies the latest directory to the website archive directory
  """
  global web_archive
  destdir = os.path.join(web_archive,datadir)
  srcdir  = os.path.join(in_path, datadir)  
  try:
    shutil.copytree(srcdir, destdir)
    logging.info("Data files copied to: "+destdir)
  except (IOError, os.error) as e:
    logging.error("Error %s", str(e)+" from: "+datadir+" to: "+web_archive)



def main():
  """
  Loops thru a number of index values,retrieved from a db query, reads rows 
  from the csv file passed on the command line
  Each row contains data for a certain station at a certain time
  The loop aggregates the data, and creates a discharge array for each station
  This array is fed to a function to create a hydrograph for each station
  """

  logging.info("*** Hydrograph process started ***")
  datadir = get_latest_datadir()
  if datadir is None:
    exit
  else:	
    data_rows = parse_frxst(datadir)
    if (data_rows is None):
      sys.exit()
    else:
    # we have data, go ahead
      do_loop(data_rows)
    # INSERT to the database
      upload_flow_data(data_rows)
      upload_model_timing(data_rows)
      copy_to_archive(datadir)
      send_alerts()

  logging.info("*** Hydrograph Process completed ***")
  # end of main()


if __name__ == "__main__":
# Get into script directory
  if (len(sys.argv) == 2):
    script_path = sys.argv[1]
  else:
  # No script path passed on command line, assume "/usr/local/sbin"
    script_path = "/usr/local/sbin"

  os.chdir(script_path)

# Get configurations
  config = ConfigParser.ConfigParser()
  config.read("hydrographs.conf")
  min_hr = config.getint("General", "min_hr")
  max_hr = config.getint("General","max_hr")
  hr_col = config.getint("General", "hr_col")
  in_path = config.get("General", "in_path")
  disch_col = config.getint("General", "disch_col")
  dt_str_col = config.getint("General", "dt_str_col")
  ts_file = config.get("General", "timestamp_file")
  data_file = config.get("General", "disch_data_file")
  log_file = config.get("General", "logfile")
  out_path = config.get("Graphs","out_path")
  out_pref = config.get("Graphs", "out_pref")
  host = config.get("Db","host")
  dbname = config.get("Db","dbname")
  user = config.get("Db","user")
  password = config.get("Db","password")
  web_archive = config.get("Web","web_archive")

  # Set up logging
  frmt='%(asctime)s %(levelname)-8s %(message)s'
  logging.basicConfig(level=logging.DEBUG, format=frmt, filename=log_file, filemode='a')
 
  # Now begin work
  main()

