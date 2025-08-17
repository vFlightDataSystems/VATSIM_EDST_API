import threading

# thread-safe global storage
data_lock = threading.Lock()
weather_data = {
    "lats": None,
    "lons": None,
    "levels": {}  # { FL: {"temp": 2Darray, "dir": 2Darray, "spd": 2Darray} }
}
