import logging
import re
from typing import Optional

import numpy as np
import requests
from lxml import etree
from flask import Blueprint, jsonify, request
from libs.weather_data_lock import weather_data, data_lock

weather_blueprint = Blueprint('weather', __name__)


def get_datis(airport):
    response = requests.get(f'https://datis.clowd.io/api/{airport}')
    json = response.json()
    if type(json) is list:
        data = []
        for datis in json:
            atis_str = datis['datis']
            data.append({
                'atis_string': atis_str,
                'letter': re.search(r'(?:INFO )(\S)', atis_str).group(1),
                'time': re.search(r'\d{4}Z', atis_str)[0],
                'type': datis['type'],
                'airport': datis['airport']
            })
        return data
    else:
        return json


@weather_blueprint.route('/metar/airport/<airport>')
def _metar(airport):
    response = requests.get(
        f'https://metar.vatsim.net/{airport}')

    metar_text = response.content.decode('utf-8')
    return jsonify([metar_text])

@weather_blueprint.route('/winds')
def winds():
    # query params
    top_lat = float(request.args.get("toplat"))
    top_lon = float(request.args.get("toplong"))
    bottom_lat = float(request.args.get("bottomlat"))
    bottom_lon = float(request.args.get("bottomlong"))
    fl = int(request.args.get("fl", 300))  # default FL300

    with data_lock:
        lats = weather_data["lats"]
        lons = weather_data["lons"]
        levels = weather_data["levels"]

        if lats is None or fl not in levels:
            return jsonify({"error": "No data loaded"}), 503

        lat_min, lat_max = sorted([bottom_lat, top_lat])
        lon_min, lon_max = sorted([bottom_lon, top_lon])

        mask = ((lats >= lat_min) & (lats <= lat_max) &
                (lons >= lon_min) & (lons <= lon_max))

        # find indices inside mask
        indices = np.where(mask)
        if indices[0].size == 0:
            return jsonify({"points": []})

        # Limit to at most 15x15 samples regardless of zoom
        MAX_DIM = 15
        unique_rows = np.unique(indices[0])
        unique_cols = np.unique(indices[1])

        keep_rows = unique_rows[np.linspace(0, len(unique_rows) - 1, min(len(unique_rows), MAX_DIM), dtype=int)]
        keep_cols = unique_cols[np.linspace(0, len(unique_cols) - 1, min(len(unique_cols), MAX_DIM), dtype=int)]

        points = []
        for i in keep_rows:
            for j in keep_cols:
                if not mask[i, j]:
                    continue
                points.append({
                    "latitude": float(round(lats[i, j], 2)),
                    "longitude": float(round(lons[i, j], 2)),
                    "wind_speed_kt": int(levels[fl]["spd"][i, j]),
                    "wind_direction_deg_true": int(levels[fl]["dir"][i, j]),
                    "temperature_c": int(levels[fl]["temp"][i, j]),
                })
    with data_lock:
        metadata = weather_data.get("wx_state")

    return jsonify({"points": points, "metadata": metadata})


@weather_blueprint.route('/sigmets')
def _get_sigmets():
    response = requests.get(
        'https://aviationweather.gov/api/data/airsigmet?format=xml')
    sigmet_list = []
    tree = etree.fromstring(response.content)
    for entry in tree.iter('AIRSIGMET'):
        try:
            sigmet_entry = {
                'text': entry.find('raw_text').text,
                'hazard': dict(entry.find('hazard').attrib),
                'area': [[p.find('longitude').text, p.find('latitude').text] for p in entry.find('area').iter('point')],
                'altitude': dict(entry.find('altitude').attrib),
                'airsigmet_type': entry.find('airsigmet_type').text,
            }
            sigmet_list.append(sigmet_entry)
        except Exception as e:
            pass
            # logging.Logger(str(e))
    return jsonify(sigmet_list)


@weather_blueprint.route('/datis/airport/<airport>')
def _get_datis(airport):
    return jsonify(get_datis(airport))
