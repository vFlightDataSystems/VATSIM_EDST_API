from dataclasses import dataclass
from io import BufferedReader, BytesIO
import pygrib
import requests
import numpy as np
from libs.weather_data_lock import weather_data, data_lock, WeatherData
from datetime import datetime, timezone

RAP_BASE_URL = 'https://nomads.ncep.noaa.gov/pub/data/nccf/com/rap/prod'
KELVIN_TO_CELSIUS = -273.15
METER_TO_FEET = 3.281
FEET_PER_FLIGHT_LEVEL = 100.0
METERS_PER_SEC_TO_KNOTS = 1.94384449

def get_rap_grib2_stream(date_str: str, cycle_hour: str, forecast_hour: str) -> BufferedReader | None:
    """Acquire a stream of RAP GRIB2 data from NOAA
    
    Args:
        date_str (str): Date string in 'YYYYMMDD' format
        cycle_hour (str): Cycle hour ('00' or '12')
        forecast_hour (str): Forecast hour (e.g., '00', '01', ...)
        
    Returns:
        BufferedReader: Stream of GRIB2 data, or None if download fails
    """
    file_name = f"rap.t{cycle_hour}z.awp130pgrbf{forecast_hour.zfill(2)}.grib2"
    url = f"{RAP_BASE_URL}/rap.{date_str}/{file_name}"

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        return(BufferedReader(BytesIO(response.content)))
    else:
        print(f"Failed to download file. HTTP {response.status_code}: {url}")
        return None

def interpolate_uv_temp_at_flight_levels(grib_buffer: BufferedReader):
    """
    Interpolate U and V wind components and temperature to flight levels  

    :param grib_buffer: BufferedReader stream of GRIB2 data from requests.raw
    """
    grbs = pygrib.open(grib_buffer)

    geopotential_height = grbs.select(name='Geopotential height', typeOfLevel='isobaricInhPa')
    u_component = grbs.select(name='U component of wind', typeOfLevel='isobaricInhPa')
    v_component = grbs.select(name='V component of wind', typeOfLevel='isobaricInhPa')
    temp_component = grbs.select(name='Temperature', typeOfLevel='isobaricInhPa')

    geopotential_height_3d = np.array([g.values for g in geopotential_height])
    u_component_3d   = np.array([g.values for g in u_component])
    v_component_3d   = np.array([g.values for g in v_component])
    temp_component_3d   = np.array([g.values for g in temp_component]) + KELVIN_TO_CELSIUS

    lats, lons = geopotential_height[0].latlons()

    geopotential_height_3d_feet = geopotential_height_3d * METER_TO_FEET
    flight_level_3d = geopotential_height_3d_feet / FEET_PER_FLIGHT_LEVEL

    fl_target = np.arange(0, 510, 10)
    level_dict = {}

    for fl in fl_target:
        temp_2d = np.full(lats.shape, np.nan)
        speed_2d = np.full(lats.shape, np.nan)
        dir_2d = np.full(lats.shape, np.nan)

        for i in range(lats.shape[0]):
            for j in range(lats.shape[1]):
                profile_fl = flight_level_3d[:, i, j]
                profile_u = u_component_3d[:, i, j]
                profile_v = v_component_3d[:, i, j]
                profile_t = temp_component_3d[:, i, j]

                if (np.any(np.isnan(profile_fl)) or np.any(np.isnan(profile_u)) or
                    np.any(np.isnan(profile_v)) or np.any(np.isnan(profile_t))):
                    continue

                u_val = np.interp(fl, profile_fl[::-1], profile_u[::-1])
                v_val = np.interp(fl, profile_fl[::-1], profile_v[::-1])
                t_val = np.interp(fl, profile_fl[::-1], profile_t[::-1])

                speed = np.sqrt(u_val**2 + v_val**2)
                direction = (270 - np.degrees(np.arctan2(v_val, u_val))) % 360

                # convert speed from m/s to knots (1 m/s = 1.94384449 kt)
                speed_kt = speed * METERS_PER_SEC_TO_KNOTS

                temp_2d[i, j] = int(round(t_val))
                speed_2d[i, j] = int(round(speed_kt))
                dir_2d[i, j]   = int(round(direction))

        level_dict[int(fl)] = {"temp": temp_2d, "spd": speed_2d, "dir": dir_2d}

    with data_lock:
        weather_data.lats = lats
        weather_data.lons = lons
        weather_data.levels = level_dict

    grbs.close()

def different_hour(new_forecast: WeatherData) -> bool:
    """Checks if the provided new forecast is newer than the existing in-memory forecast

    Args:
        new_forecast (WeatherData): the new forecast data to compare

    Returns:
        bool: True if the new forecast is different from the previous forecast hour, False otherwise
    """
    # read previous forecast from in-memory store
    with data_lock:
        prev_state = weather_data
    if prev_state.forecast_hour is None:
        # no previous state -> treat as new
        return True
    return new_forecast != prev_state.forecast_hour

@dataclass
class RAPDateInfo:
    date_str: str
    cycle_hour: str
    forecast_hour: str

# Function to get the current RAP forecast date and time, and build file path info
def get_date() -> RAPDateInfo:
    """Gets the current datetime and formulates the string for use in RAP model fetching

    Returns:
        RAPDateInfo: Current forecast date information
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime('%Y%m%d')
    cycle_hour = '12' if now.hour >= 12 else '00'
    forecast_hour = '00'
    return RAPDateInfo(date_str, cycle_hour, forecast_hour)

