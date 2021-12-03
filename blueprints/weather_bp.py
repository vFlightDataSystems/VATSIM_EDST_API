import re

import requests
from lxml import etree
from flask import Blueprint, jsonify

weather_blueprint = Blueprint('weather', __name__)


@weather_blueprint.route('/metar/airport/<airport>')
def _metar(airport):
    response = requests.get(
        f'https://www.aviationweather.gov/adds/dataserver_current'
        f'/httpparam?dataSource=metars&requestType=retrieve&format=xml&stationString={airport}&hoursBeforeNow=2')

    tree = etree.fromstring(response.content)
    metar_list = [e.text for e in tree.iter('raw_text')]

    return jsonify(metar_list)


@weather_blueprint.route('/datis/airport/<airport>')
def _get_datis(airport):
    response = requests.get(f'https://datis.clowd.io/api/{airport}')
    json = response.json()
    if type(json) is list:
        data = []
        for datis in json:
            atis_str = datis['datis']
            data.append({
                'datis': atis_str,
                'letter': re.search(r'(?:INFO )(\S)', atis_str).group(1),
                'time': re.search(r'\d{4}Z', atis_str)[0],
                'type': datis['airport'],
                'airport': datis['airport']
            })
        return jsonify(data)
    else:
        return jsonify(json)
