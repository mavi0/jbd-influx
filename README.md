# jbd-influx
Read stats from JDB BMS and send to InfluxDB

Hard coded for JDB-SP04S034

Needs the following environment variables set:

``` python
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
```

Based on https://github.com/tgalarneau/bms/blob/main/jbdbms-4-socket-2temps.py