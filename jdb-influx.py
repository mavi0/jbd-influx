#!/usr/bin/env python3
# using python 3.9 
    
from bluepy.btle import Peripheral, DefaultDelegate, BTLEException
import struct
import argparse
import sys
import time, datetime, json
import binascii
import socket
import atexit
import logging
import influxdb_client
import os
import requests
import sys
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)
logging.basicConfig()
logger.setLevel(logging.INFO)

INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "testing_db")
INFLUX_ORG = os.getenv("INFLUX_ORG", "")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_URL = os.getenv("INFLUX_URL", "")

DEBUG = os.getenv("DEBUG", False)          # Disable sending to Influx, just print to terminal
TEMP_C = os.getenv("TEMP_F", False)        # Convert temp to american-ness
INTERVAL = os.getenv("INTERVAL", 10)       # Interval between grabbing stats
BLE_ADDRESS = os.getenv("BLE_ADDRESS", "00:00:00:00:00:00")
MEASUREMENT = os.getenv("MEASUREMENT", "jdbms")
MODEL_NUMBER = os.getenv("MODEL_NUMBER", "JDB-SP04S034")

def cell_info_1(data):			# process pack info
    r = {}
    results = {}
    infodata = data
    i = 4                       # Unpack into variables, skipping header bytes 0-3
    volts, amps, remain, capacity, cycles, mdate, balance1, balance2 = struct.unpack_from('>HhHHHHHH', infodata, i)
    r['volts']    = volts/100
    r['amps']     = amps/100
    r['capacity'] = capacity/100
    r['remain']   = remain/100
    r['watts']    = volts*amps  							# adding watts field for dbase
    bal1     = (format(balance1, "b").zfill(16))		
    r['c16'] = int(bal1[0:1])							
    r['c15'] = int(bal1[1:2])							# using balance1 bits for 16 cells
    r['c14'] = int(bal1[2:3])							# balance2 is for next 17-32 cells - not using
    r['c13'] = int(bal1[3:4])
    r['c12'] = int(bal1[4:5])							# bit shows (0,1) charging on-off
    r['c11'] = int(bal1[5:6])
    r['c10'] = int(bal1[6:7])
    r['c09'] = int(bal1[7:8])
    r['c08'] = int(bal1[8:9])
    r['c07'] = int(bal1[9:10])
    r['c06'] = int(bal1[10:11])
    r['c05'] = int(bal1[11:12])
    r['c04'] = int(bal1[12:13])        
    r['c03'] = int(bal1[13:14])
    r['c02'] = int(bal1[14:15])
    r['c01'] = int(bal1[15:16])  
    
    results["fields"] = r

    logger.info("Collected Cell Info 1")

    send_data("cell_info_1", results)
    
def cell_info_2(data):
    r = {}
    results = {}
    infodata = data  
    i = 0                          # unpack into variables, ignore end of message byte '77'
    protect,vers,percent,fet,cells,sensors,temp1,temp2,b77 = struct.unpack_from('>HBBBBBHHB', infodata, i)
    r["percent"] = percent
    r["cells"] = cells
    r["fet"] = fet
    r["temp1"] = (temp1-2731)/10
    r["temp2"] = (temp2-2731)/10		            	# fet 0011 = 3 both on ; 0010 = 2 disch on ; 0001 = 1 chrg on ; 0000 = 0 both off
    r["protect"] = protect
    prt = (format(protect, "b").zfill(16))	        	# protect trigger (0,1)(off,on)
    r["overvoltage"] = int(prt[0:1])		        	# overvoltage
    r["undervoltage"] = int(prt[1:2])		        	# undervoltage
    r["pack_overvoltage"] = int(prt[2:3])		    	# pack overvoltage
    r["pack_undervoltage"] = int(prt[3:4])			    # pack undervoltage 
    r["current_over_temp"] = int(prt[4:5])			    # current over temp
    r["current_under_temp"] = int(prt[5:6])			    # current under temp
    r["discharge_over_temp"] = int(prt[6:7])			# discharge over temp
    r["discharge_under_temp"] = int(prt[7:8])			# discharge under temp
    r["charge_over_curent"] = int(prt[8:9])			    # charge over current
    r["discharge_over_current"] = int(prt[9:10])		# discharge under current
    r["short_circuit"] = int(prt[10:11])		        # short circuit
    r["ic_failure"] = int(prt[11:12])                   # ic failure
    r["fet_config_porblem"] = int(prt[12:13])		    # fet config problem
    results["fields"] = r

    logger.info("Collected Cell Info 2")

    send_data("cell_info_2", results)



def cell_info_3(data):			                # process cell voltages
    # global cells1
    r = {}
    results = {}
    celldata = data
    i = 4                       # Unpack into variables, skipping header bytes 0-3
    cell1, cell2, cell3, cell4 = struct.unpack_from('>HHHH', celldata, i)
    cells1 = [cell1, cell2, cell3, cell4] 	# needed for max, min, delta calculations

    cellmin = min(cells1)
    cellmax = max(cells1)
    delta = cellmax-cellmin

    
    r["cellmin"] = [cellmin]
    r["cellmax"] = [cellmax]
    r["delta"] = [delta]
    r["cell1"] = [cell1]
    r["cell2"] = [cell2]
    r["cell3"] = [cell3]
    r["cell4"] = [cell4]

    results["fields"] = r

    logger.info("Collected Cell Info 3")

    send_data("cell_info_3", results)
                    
class BMSDelegate(DefaultDelegate):		    # notification responses
    def __init__(self):
        DefaultDelegate.__init__(self)
    def handleNotification(self, cHandle, data):
        hex_data = binascii.hexlify(data) 		# Given raw bytes, get an ASCII string representing the hex values
        text_string = hex_data.decode('utf-8')  # check incoming data for routing to decoding routines
        if text_string.find('dd04') != -1:	                             # x04 (1-8 cells)	
        	cell_info_3(data)
        elif text_string.find('dd03') != -1:                             # x03
        	cell_info_1(data)
        #elif text_string.find('77') != -1 and len(text_string) == 38:	 # x04 (9-16 cells)
        #	cellvolts2(data)
        elif text_string.find('77') != -1:	 # x03
            cell_info_2(data)	

def send_data(tag, results):
    results["measurement"] = MEASUREMENT
    tags = {}
    tags["model_number"] = MODEL_NUMBER
    tags["cell_info"] = tag
    results["tags"] = tags
    results["time"] = datetime.datetime.now().astimezone().isoformat()
    logger.info("{}".format(json.dumps(
            results,
            sort_keys=True,
            indent=2,
            separators=(',', ': '))))
    if not DEBUG:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=results)

try:
    logger.info('attempting to connect')		
    bms = Peripheral(BLE_ADDRESS, addrType="public")
except BTLEException as ex:
    time.sleep(10)
    logger.warn('2nd try connect')
    bms = Peripheral(BLE_ADDRESS, addrType="public")
except BTLEException as ex:
    logger.error('cannot connect')
    exit()
else:
    logger.info('connected ' + BLE_ADDRESS)

bms.setDelegate(BMSDelegate())		# setup delegate for notifications

while True:
    result = bms.writeCharacteristic(0x15,b'\xdd\xa5\x03\x00\xff\xfd\x77',False)		# write x03 w/o response cell info
    bms.waitForNotifications(5)
    result = bms.writeCharacteristic(0x15,b'\xdd\xa5\x04\x00\xff\xfc\x77',False)		# write x04 w/o response cell voltages
    bms.waitForNotifications(5)
    time.sleep(INTERVAL)