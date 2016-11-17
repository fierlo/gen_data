#! /usr/bin/python2
#
## Python program to parse the Generator Output Capabilities XML files
## from the IESO website. http://reports.ieso.ca/public/
##
## Should be modified to download latest daily, after parsing is figured out.
##
##
# Import XML parsing modules

from xml.dom import minidom
import re
from datetime import date
from datetime import timedelta
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import time
import getopt
import sys
import urllib
import pg
import string

def main():
    # Lines below to set date to yesterday. Easier to get the XML from a shell script
    # and then execute this with the appropriate flag. Keep the code here in case you
    # want to modify it later to grab the data directly from the reports site.
    #
    yesterday = date.today() - timedelta(days=1)
    y = yesterday.strftime('%Y%m%d')
        
    try:
	    opts, args = getopt.getopt(sys.argv[1:],  "f:c")
    except getopt.GetoptError,  err:
        print '',  str(err)
        sys.exit(2)
    for o,  a in opts:
        if o == "-f":
            source = a
	    total_gen(source)
        elif o == "-c":
	    chart = a
	    chart_data()
        else:
            assert False,  "unhandled option"
    
# Generate all the charts if the only command line argument is -c

def chart_data():
	''' Get the chart data. Accepts exactly one argument, the chart_type. This will be
	called multiple times to generate all the different charts. Generate one chart for
	each station, fuel_type, and others as required. '''
	
	# Create a dictionary with the values being the data from the database which will be used to make
	# the chart.

	queries = {'hourly': 'select hour, cast(sum(tot_output)/avg(entries) as numeric(10,2)) from hourly_data group by 1 order by 1',
			'nuclear': 'select hour, cast(100.0*sum(tot_output)/sum(tot_capability) as numeric(5,2)) from hourly_data where name=\'Nuclear\' group by hour order by 1',
			'wind': 'select hour, cast(100.0*sum(tot_output)/sum(tot_capability) as numeric(5,2)) from hourly_data where name=\'Wind\' group by hour order by 1',
			'gas': 'select hour, cast(100.0*sum(tot_output)/sum(tot_capability) as numeric(5,2)) from hourly_data where name=\'Gas\' group by hour order by 1',
			'coal': 'select hour, cast(100.0*sum(tot_output)/sum(tot_capability) as numeric(5,2)) from hourly_data where name=\'Coal\' group by hour order by 1',
			'hydro': 'select hour, cast(100.0*sum(tot_output)/sum(tot_capability) as numeric(5,2)) from hourly_data where name=\'Hydro\' group by hour order by 1',
			'other': 'select hour, cast(100.0*sum(tot_output)/sum(tot_capability) as numeric(5,2)) from hourly_data where name=\'Other\' group by hour order by 1',
                        'biofuel': 'select hour, cast(100.0*sum(tot_output)/sum(tot_capability) as numeric(5,2)) from hourly_data where name=\'Biofuel\' group by hour order by 1'}

	chart_hourly = psql_query(queries['hourly'])

	# Traverse through the query dictionary, generating all the results.
	for key, value in queries.items():
		if key=='hourly':
			pass
		else:
			chart_values = psql_query(value)
			plot_chart(chart_values,chart_hourly,key)



def plot_chart(data,grid_total,key):
	''' Plot the chart. Store the chart as a PNG to the default location of '/srv/www/htdocs/chorah/'
	Take different courses of actions depending on which data series is being plotted. Accepts three
	inputs: data, total grid power and key. data/total grid power are a list of of tuples ordered in
	the form of (hour(int), capacity(float)). '''

	local_png = '/srv/http/chorah/' + string.capitalize(key) + '.png'
	
	# Plot the chart. Two series (data, grid_total). X values are 0 to 23. Use 'key'
	# for making the legend on the chart. Y1 is data, and Y2 is grid_total.
	
	x = range(0,24)
	y1 = []
	y2 = []
	for i in range(0,24):
		y1.append(data[i][1])
		y2.append(grid_total[i][1])
	fig = plt.figure()
	ax1 = fig.add_subplot(111)
	ax1.plot(x,y1,'bo')
	ax1.set_xlabel('hour')
	ax1.set_ylabel('Capacity Factor (%)',color='b')
	ax1.xaxis.set_major_locator(MaxNLocator(7))
	ax1.axis('tight')
	for x1 in ax1.get_yticklabels():
		x1.set_color('b')
	plt.ylim(0,100)


	ax2 = ax1.twinx()
	ax2.plot(x,y2,'rx')
	ax2.set_ylabel('Grid Demand (MW)', color='r')
	ax2.xaxis.set_major_locator(MaxNLocator(7))
	ax2.axis('tight')
	for x1 in ax2.get_yticklabels():
		x1.set_color('r')
	plt.title(string.capitalize(key))

	fig.savefig(local_png,format='png')


def psql_query(query):
	''' Opens connection to the database, submits query, and returns the results. '''

	con = pg.connect(dbname='power', host='localhost', user='chris')

	results = con.query(query)
	
	results=results.getresult()

	return results

# Default source http://reports.ieso.ca/public/GenOutputCapability/PUB_GenOutputCapability_20100129.xml
# If no argument given, get yesterday's data.

def date_info(source_doc):
    ''' date_info parses the path/filename and extracts the date information from the 
    filename portion. It is written in PUB_GenOutputCapability_YYYYMMDD.xml$ '''
    filename = source_doc.split('/')[-1]
    year, month, day = filename[-12:-8],  filename[-8:-6], filename[-6:-4]
    return year,  month,  day
    
def generator_list(source_doc):
    ''' generator_list takes a source document as an argument, and returns a list of generators.
    The list of generators is a list of XML nodes, to be parsed further by generator '''
    
    # XML parsing is performed in this step. It's main purpose is to keep everything
    # in a nice, easy to manipulate format for the rest of the program.
    # It gets elements by their tag, and returns a list of the generators.

    xmldoc = minidom.parse(source_doc)
    imodoc = xmldoc.childNodes[1]
    imobody = imodoc.childNodes[3]
    generator_list = imobody.childNodes[3]
    gen_list = generator_list.getElementsByTagName('Generator')
    return gen_list

def generator(gen_list, i):
    ''' generator takes the generator list and a child node (must be odd number) as arguments
    and returns name, fuel_type and output_list and cap_list. output_list and cap_list are both XML
    objects which are used in performance function. '''
    
    current_gen = gen_list[i]
    gen_name = current_gen.childNodes[1]
    name = gen_name.firstChild.data
    gen_type = current_gen.childNodes[3]
    fuel_type = gen_type.firstChild.data
    output_list = current_gen.getElementsByTagName('Output')
    cap_list = current_gen.getElementsByTagName('Capability')
    return name,  fuel_type,  output_list,  cap_list

def performance(output_list,  cap_list):
    ''' performance takes the output_list produced by gen_name and returns a dictionary
    consisting of an hour key, and a tuple for the value. Tuple form is (capability, output). '''
    
    # Initialize empty dictionary
    
    total_output = dict()
    
    # Walk through the output and capabilities lists. Manipulation happening mostly because of
    # XML objects. There may be a quicker way to do this. Look it up sometime.
    
    for i in range(len(output_list)):
        a = output_list[i]
	try:	
		b = a.childNodes[3]
		c = int(b.firstChild.data)
	except IndexError:
		c=0
        d = cap_list[i]
        e = d.childNodes[3]
        f = int(e.firstChild.data)
        total_output[i+1]=(f, c)
    
    return total_output

def file_output(year,  month,  day,  fuel_type,  name,  total_output):
    ''' file_output takes the date info, fuel_type, name and total_output (dictionary[hour] = (capability, output)
    and inserts each hourly value into the PostgreSQL database as a row. Could be substituted for another database
    or output type with minimal effort.''' 
    
    con = pg.connect(dbname='power',  host='localhost',  user='chris')
        
    # Define the different types of generation using a key/value pair.

    types = {'NUCLEAR': 1,  'WIND': 2,  'COAL': 3, 'GAS': 4,  'HYDRO(>20MW)': 5,  'OTHER': 6, 'HYDRO': 5 , 'SOLAR': 7, 'BIOFUEL': 8 }
    type_id = str(types[fuel_type])
        
    # A for loop which runs through all the output, and inserts the hourly data for a single generator for the previous day.

    for i in range(len(total_output)):
        hour = str(i)
        # Assign values, to make the insert query easier to read.

	capability,  output = total_output.values()[i][0],  total_output.values()[i][1]
        
	# Prepare query. All values must be inserted as strings, even though most are integers.
	
	insert_query = 'insert into hourly values(' + type_id + ',\'' + name + '\',' + str(capability) + ',' + str(output) + ',' + hour + ','  + 'TIMESTAMP \'' + str(year) + '-' + str(month) + '-' + str(day) + ' ' + hour + ':00:00' + '\'' + ')'
       
	# Commit query to database. 

	con.query(insert_query)
        
    res = con.close()

def total_gen(source_doc):
    ''' total_gen accepts source doc, and runs through all generators and prints the total
    output of each. '''

    # Get a list of the generators from the generator_list function. Extract the date info
    # from the source document.

    gen_list = generator_list(source_doc)
    year, month,  day = date_info(source_doc)
    
    # Execute a for loop over the entirety of the generator list. 

    for i in range(0, len(gen_list)):
        # Get the name, fuel type, output and capabilities for the generator.
	generator_info = generator(gen_list,  i)
	
	# Figure out the total output for the day. It seems a little silly to have this line,
	# but I haven't refactored this enough to eliminate it at this point. It works, so I
	# will leave it until it becomes an issue.
        total_output = performance(generator_info[2],  generator_info[3])
     
     	# Output the data to a file (in this case, a database)
        file_output(year,  month,  day,  generator_info[1],  generator_info[0],  total_output)

if __name__ == "__main__":
    main()
