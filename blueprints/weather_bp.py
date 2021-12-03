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
    return jsonify(response.json())
