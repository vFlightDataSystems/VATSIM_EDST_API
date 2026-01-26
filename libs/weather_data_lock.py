import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

# thread-safe lock shared by callers
data_lock = threading.Lock()

@dataclass
class WindGridState:
    process_date: str
    process_cycle: str
    forecast_hour: str
    processed_at_utc: str

@dataclass
class WindGridData:
    lats: Optional[Any] = None           # expected: 2D numpy array or None
    lons: Optional[Any] = None           # expected: 2D numpy array or None
    levels: Dict[int, Dict[str, Any]] = field(default_factory=dict)  # { FL: {"temp": 2Darray, "dir": 2Darray, "spd": 2Darray} }
    wx_state: Optional[WindGridState] = None   

# global instance used throughout the app
weather_data = WindGridData()