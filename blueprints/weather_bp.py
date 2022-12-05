import logging
import re
from typing import Optional

import requests
from lxml import etree
from flask import Blueprint, jsonify

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
        f'https://www.aviationweather.gov/adds/dataserver_current'
        f'/httpparam?dataSource=metars&requestType=retrieve&format=xml&stationString={airport}&hoursBeforeNow=2')

    tree = etree.fromstring(response.content)
    metar_list = [e.text for e in tree.iter('raw_text')]

    return jsonify(metar_list)


@weather_blueprint.route('/sigmets')
def _get_sigmets():
    response = requests.get(
        'https://www.aviationweather.gov/adds/dataserver_current'
        '/httpparam?dataSource=airsigmets&requestType=retrieve&format=xml&hoursBeforeNow=6')
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
