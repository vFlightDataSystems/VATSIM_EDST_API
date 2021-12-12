from flask import Blueprint, g, jsonify
from pymongo import MongoClient

navdata_blueprint = Blueprint('navdata', __name__)


@navdata_blueprint.route('/airport/<airport>')
def _get_airport(airport: str):
    client: MongoClient = g.mongo_reader_client
    airport_data = client.navdata.airports.find_one({'icao': airport.upper()}, {'_id': False})
    return jsonify(airport_data)


@navdata_blueprint.route('/airport/<airport>/procedures')
def _get_airport_procedures(airport: str):
    client: MongoClient = g.mongo_reader_client
    data = list(client.navdata.procedures.find({'routes': {'$elemMatch': {'airport': airport.upper()}}}, {'_id': False}))
    for row in data:
        row['routes'] = list(filter(lambda r: r['airport'] == airport, row['routes']))
    return jsonify(data)


@navdata_blueprint.route('/airway/<airway>')
def _get_airway(airway: str):
    client: MongoClient = g.mongo_reader_client
    airway_data = list(client.navdata.airways.find({'airway': airway.upper()}, {'_id': False}))
    return jsonify(airway_data)


@navdata_blueprint.route('/waypoint/<waypoint>')
def _get_waypoint(waypoint: str):
    client: MongoClient = g.mongo_reader_client
    waypoint_data = list(client.navdata.waypoints.find({'waypoint_id': waypoint.upper()}, {'_id': False}))
    return jsonify(waypoint_data)


@navdata_blueprint.route('/procedure/<procedure>')
def _get_procedure(procedure: str):
    client: MongoClient = g.mongo_reader_client
    procedure_data = client.navdata.procedures.find_one({'procedure': procedure.upper()}, {'_id': False})
    return jsonify(procedure_data)
