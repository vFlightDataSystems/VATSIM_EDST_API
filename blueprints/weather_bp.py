import re
from typing import Optional

import requests
from lxml import etree
from flask import Blueprint, jsonify

from libs.lib import get_all_connections

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


def get_vatsim_atis(airport: str) -> Optional[list]:
    if (connections := get_all_connections()) is not None:
        if 'atis' in connections.keys():
            if atis_connection := next(
                    filter(lambda x: x['callsign'] == f'{airport.upper()}_ATIS', connections['atis']), None):
                if atis_connection['text_atis']:
                    atis_str = ' '.join(atis_connection['text_atis'])
                    return [{
                        'atis_string': atis_str,
                        'letter': atis_connection['atis_code'],
                        'time': re.search(r'\d{4}Z', atis_str)[0],
                        'type': 'vatsim_atis',
                        'airport': airport
                    }]
    return None


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
    tree = etree.fromstring(response.content)
    sigmet_list = [e.text for e in tree.iter('raw_text')]
    return jsonify(sigmet_list)


@weather_blueprint.route('/datis/airport/<airport>')
def _get_datis(airport):
    return jsonify(get_datis(airport))


@weather_blueprint.route('/atis/vatsim/airport/<airport>')
def _get_vatsim_atis(airport):
    if (atis := get_vatsim_atis(airport)) is not None:
        return jsonify(atis)
    else:
        return jsonify(get_datis(airport))
