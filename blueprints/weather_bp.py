import logging
import re
from typing import Optional

import requests
from lxml import etree
from flask import Blueprint, jsonify, request
from libs.helpers import haversine_distance

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

@weather_blueprint.route('/sigmets')
def _get_sigmets():
  centerlat = request.args.get('centerLat')
  centerlon = request.args.get('centerLon')
  
  response = requests.get(
    'https://aviationweather.gov/api/data/airsigmet?format=json&types=sigmet').json()
  
  # Only filter if we have both lat and lon
  if centerlat and centerlon:
    centerlat = float(centerlat)
    centerlon = float(centerlon)
    
    # Filter sigmets within 150nm
    filtered_sigmets = []
    for sigmet in response:
      # Check if any point in sigmet polygon is within range
      coords = sigmet.get('coords', [])
      for coord in coords:
        dist = haversine_distance(centerlat, centerlon, 
              coord['lat'], coord['lon'])
        if dist <= 150:
          filtered_sigmets.append(sigmet)
          break
    return jsonify(filtered_sigmets)
  
  return jsonify(response)


@weather_blueprint.route('/datis/airport/<airport>')
def _get_datis(airport):
    return jsonify(get_datis(airport))
