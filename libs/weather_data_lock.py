import threading

# thread-safe global storage
data_lock = threading.Lock()
weather_data = {
    "lats": None,
    "lons": None,
    "levels": {},  # { FL: {"temp": 2Darray, "dir": 2Darray, "spd": 2Darray} }
    "wx_state": None,           # {'String': 'YYYYMMDD', 'Cycle': '00'|'12', 'Forecast Hour': '00'}
    "last_updated_utc": None,   # ISO timestamp string set when interpolate_uv_temp_at_flight_levels finishes
    "grib_path": None,          # optional: path to last downloaded grib file
}
