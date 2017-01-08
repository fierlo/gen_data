#! /bin/bash


# Set the target date (yesterday, generally).

target=$(date --date='2 day ago' +%Y%m%d)

cd /home/chris/python/chorah

# Download the report from the IESO site.

wget http://reports.ieso.ca/public/GenOutputCapability/PUB_GenOutputCapability_${target}.xml 

# Do the heavy lifting for the output capability list via a Python program, gen_hourly.py, also included.

python2 /home/chris/python/chorah/gen_hourly.py -f /home/chris/python/chorah/PUB_GenOutputCapability_${target}.xml

# Drop the old station data and hourly data for each station, and then regenerate these tables based on
# the updated data. Some stations are excluded because they are in commissioning, and thus have 0/0 which
# is not allowed as you have a division by zero.

psql power -c "drop table station_data"

psql power -c "drop table hourly_data"

psql power -c "create table station_data as with station_max as (select station, max(capability) as max_cap from hourly group by 1) select fuel_type.name, hourly.station, cast(100.0*sum(output)/(station_max.max_cap*count(hourly.station)) as numeric(5,2)) as capacity, station_max.max_cap as capability, sum(output) as tot_output, (station_max.max_cap*count(hourly.station)) as tot_capability, sum(capability) as sum_cap, count(hourly.station) as entries from hourly join station_max on station_max.station=hourly.station join fuel_type on fuel_type.fuel_id = hourly.fuel_id where station_max.max_cap>0 group by hourly.station, fuel_type.name, station_max.max_cap"

psql power -c "create table hourly_data as with station_hourly_max as (select station, hour, max(capability) as max_cap from hourly group by 1,2) select fuel_type.name, hourly.station, hourly.hour, cast(100.0*sum(output)/(station_hourly_max.max_cap*count(hourly.station)) as numeric(5,2)) as capacity, station_hourly_max.max_cap as capability, sum(output) as tot_output, (station_hourly_max.max_cap*count(hourly.station)) as tot_capability, sum(capability) as sum_cap, count(hourly.station) as entries from hourly join station_hourly_max on station_hourly_max.station=hourly.station and station_hourly_max.hour=hourly.hour join fuel_type on fuel_type.fuel_id = hourly.fuel_id where station_hourly_max.max_cap>0 group by hourly.station, hourly.hour, fuel_type.name,station_hourly_max.max_cap"

# Generate the plots using the python2 script with the -c flag

python2 /home/chris/python/chorah/gen_hourly.py -c
