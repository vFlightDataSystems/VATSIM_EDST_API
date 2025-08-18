import logging
import re
from typing import Optional

import requests
from lxml import etree
from flask import Blueprint, jsonify, request
from shapely.geometry import shape, Point, Polygon
import json

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
    artcc_id = request.args.get('artcc')
    response = requests.get(
        'https://aviationweather.gov/api/data/airsigmet?format=json').json()

    if artcc_id:
        # Load ARTCC boundary polygon
        with open('resources/ArtccBoundaries.geojson') as f:
            geojson = json.load(f)
        artcc_poly = None
        for feature in geojson['features']:
            if feature['properties']['id'].upper() == artcc_id.upper():
                artcc_poly = shape(feature['geometry'])
                break
        if not artcc_poly:
            return jsonify([])  # or handle error

        filtered_sigmets = []
        for sigmet in response:
            coords = sigmet.get('coords', [])
            for coord in coords:
                pt = Point(coord['lon'], coord['lat'])
                if artcc_poly.contains(pt):
                    filtered_sigmets.append(sigmet)
                    break
                # Check distance to polygon boundary
                if artcc_poly.exterior.distance(pt) * 60 <= 150:  # degrees to nm approx
                    filtered_sigmets.append(sigmet)
                    break
        return jsonify(filtered_sigmets)

    return jsonify(response)

@weather_blueprint.route('/datis/airport/<airport>')
def _get_datis(airport):
    return jsonify(get_datis(airport))
