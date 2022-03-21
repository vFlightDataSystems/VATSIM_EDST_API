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
    data = list(client.navdata.procedures.find({'airport': airport.upper()}, {'_id': False}))
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


@navdata_blueprint.route('/<artcc>/vor')
def _get_artcc_vor_list(artcc: str):
    client: MongoClient = g.mongo_reader_client
    vor_list = set(client.navdata.waypoints.find({'artcc_low': artcc.upper(), 'type': {'$regex': '.*VOR.*'}},
                                                 {'_id': False})) \
        .union(set(client.navdata.waypoints.find({'artcc_high': artcc.upper(), 'type': {'$regex': '.*VOR.*'}},
                                                 {'_id': False})))
    return jsonify(list(vor_list))


@navdata_blueprint.route('/procedure/<procedure>')
def _get_procedure(procedure: str):
    client: MongoClient = g.mongo_reader_client
    procedure_data = list(client.navdata.procedures.find({'procedure': procedure.upper()}, {'_id': False}))
    return jsonify(procedure_data)
