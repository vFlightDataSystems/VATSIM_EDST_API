from flask import Blueprint, g, jsonify

navdata_blueprint = Blueprint('navdata', __name__)


@navdata_blueprint.route('/airport/<airport>')
def _get_airport(airport: str):
    client = g.mongo_nav_client
    airport_data = client.navdata.airports.find_one({'icao': airport.upper()}, {'_id': False})
    return jsonify(airport_data)


@navdata_blueprint.route('/airport/<airport>/procedures')
def _get_airport_procedures(airport: str):
    client = g.mongo_nav_client
    data = list(client.navdata.procedures.find({'airports': {'$elemMatch': {'airport': airport.upper()}}}, {'_id': False}))
    for row in data:
        airports = row['airports']
        row['runways'] = airports[0]['runways']
        del row['airports']
    return jsonify(data)


@navdata_blueprint.route('/airway/<airway>')
def _get_airway(airway: str):
    client = g.mongo_nav_client
    airway_data = list(client.navdata.airways.find({'airway': airway.upper()}, {'_id': False}))
    return jsonify(airway_data)


@navdata_blueprint.route('/waypoint/<waypoint>')
def _get_waypoint(waypoint: str):
    client = g.mongo_nav_client
    waypoint_data = list(client.navdata.waypoints.find({'waypoint_id': waypoint.upper()}, {'_id': False}))
    return jsonify(waypoint_data)


@navdata_blueprint.route('/procedure/<procedure>')
def _get_procedure(procedure: str):
    client = g.mongo_nav_client
    procedure_data = client.navdata.procedures.find_one({'procedure': procedure.upper()}, {'_id': False})
    return jsonify(procedure_data)
