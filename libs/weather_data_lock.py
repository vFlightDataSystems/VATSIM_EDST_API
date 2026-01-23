import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

# thread-safe lock shared by callers
data_lock = threading.Lock()

@dataclass
class WeatherData:
    lats: Optional[Any] = None           # expected: 2D numpy array or None
    lons: Optional[Any] = None           # expected: 2D numpy array or None
    levels: Dict[int, Dict[str, Any]] = field(default_factory=dict)  # { FL: {"temp": 2Darray, "dir": 2Darray, "spd": 2Darray} }
    process_date: Optional[str] = None    # 'YYYYMMDD'
    process_cycle: Optional[str] = None   # '00' or '12'
    forecast_hour: Optional[str] = None  # '00', '01', ..., '18'
    processed_at_utc: Optional[str] = None  # ISO format timestamp
    wx_state: Optional[Dict[str, str]] = None           # {'String': 'YYYYMMDD', 'Cycle': '00'|'12', 'Forecast Hour': '00'}

# global instance used throughout the app
weather_data = WeatherData()