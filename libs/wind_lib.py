import pygrib
import requests
import numpy as np
from libs.weather_data_lock import weather_data, data_lock
import json
from datetime import datetime
import os
import csv

# Function to download the latest RAP GRIB2 file based on the current date and cycle hour
def download_rap_grib2(date_str, cycle_hour, forecast_hour, save_path):
    base_url = 'https://nomads.ncep.noaa.gov/pub/data/nccf/com/rap/prod'
    file_name = f"rap.t{cycle_hour}z.awp130pgrbf{forecast_hour.zfill(2)}.grib2"
    url = f"{base_url}/rap.{date_str}/{file_name}"

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded: {save_path}")
    else:
        print(f"Failed to download file. HTTP {response.status_code}: {url}")

# Function to interpolate U, V wind components and temperature to flight levels and save to CSV files
def interpolate_uv_temp_at_flight_levels(grib_file):
    grbs = pygrib.open(grib_file)

    hgt_grbs = grbs.select(name='Geopotential height', typeOfLevel='isobaricInhPa')
    u_grbs = grbs.select(name='U component of wind', typeOfLevel='isobaricInhPa')
    v_grbs = grbs.select(name='V component of wind', typeOfLevel='isobaricInhPa')
    t_grbs = grbs.select(name='Temperature', typeOfLevel='isobaricInhPa')

    hgt_3d = np.array([g.values for g in hgt_grbs])
    u_3d   = np.array([g.values for g in u_grbs])
    v_3d   = np.array([g.values for g in v_grbs])
    t_3d   = np.array([g.values for g in t_grbs]) - 273.15

    lats, lons = hgt_grbs[0].latlons()

    hgt_ft = hgt_3d * 3.281
    fl_3d = hgt_ft / 100.0

    fl_target = np.arange(0, 510, 10)
    level_dict = {}

    for fl in fl_target:
        temp_2d = np.full(lats.shape, np.nan)
        speed_2d = np.full(lats.shape, np.nan)
        dir_2d = np.full(lats.shape, np.nan)

        for i in range(lats.shape[0]):
            for j in range(lats.shape[1]):
                profile_fl = fl_3d[:, i, j]
                profile_u = u_3d[:, i, j]
                profile_v = v_3d[:, i, j]
                profile_t = t_3d[:, i, j]

                if (np.any(np.isnan(profile_fl)) or np.any(np.isnan(profile_u)) or
                    np.any(np.isnan(profile_v)) or np.any(np.isnan(profile_t))):
                    continue

                u_val = np.interp(fl, profile_fl[::-1], profile_u[::-1])
                v_val = np.interp(fl, profile_fl[::-1], profile_v[::-1])
                t_val = np.interp(fl, profile_fl[::-1], profile_t[::-1])

                speed = np.sqrt(u_val**2 + v_val**2)
                direction = (270 - np.degrees(np.arctan2(v_val, u_val))) % 360

                temp_2d[i, j] = int(round(t_val))
                speed_2d[i, j] = int(round(speed))
                dir_2d[i, j]   = int(round(direction))

        level_dict[int(fl)] = {"temp": temp_2d, "spd": speed_2d, "dir": dir_2d}

    with data_lock:
        weather_data["lats"] = lats
        weather_data["lons"] = lons
        weather_data["levels"] = level_dict

    grbs.close()

# Function to get the current RAP forecast date and time, and build file path info
def get_date():
    now = datetime.utcnow()
    date_str = now.strftime('%Y%m%d')
    cycle_hour = '12' if now.hour >= 12 else '00'
    forecast_hour = '00'
    save_path = 'rap_latest.grib2'

    # Store state in JSON format
    output = {'String': date_str, 'Cycle': cycle_hour, 'Forecast Hour': forecast_hour}
    with open('wx_state.json', 'w') as f:
        json.dump(output, f, indent=4)

    return date_str, cycle_hour, forecast_hour, save_path

# Function to check if new forecast hour differs from previously stored state
def check_state(new_forecast):
    f = open('state.json')
    data = json.load(f)

    if new_forecast != data['Forecast Hour']:
        output = True
    else:
        output = False
    return output

# Wrapper function to execute the full workflow conditionally based on forecast state
def run_grid():
    date_str, cycle_hour, forecast_hour, save_path = get_date()
    state_check = check_state(forecast_hour)

    if state_check == True:
        download_rap_grib2(date_str, cycle_hour, forecast_hour, save_path)
        interpolate_uv_temp_at_flight_levels(save_path)
        output = 'Completed'
    else:
        output = 'Error, forecast is the same as previous forecast'

    return output
