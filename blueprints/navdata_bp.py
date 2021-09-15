from flask import Blueprint, g, jsonify

navdata_blueprint = Blueprint('navdata', __name__)


@navdata_blueprint.route('/airport/<airport>')
def _get_airport(airport):
    client = g.mongo_nav_client
    airport_data = next(client.navdata.airports.find({'icao': airport}), None)
    return jsonify(airport_data)


@navdata_blueprint.route('/airway/<airway>')
def _get_airway(airway):
    client = g.mongo_nav_client
    airway_data = next(client.navdata.airways.find({'airway': airway}), None)
    return jsonify(airway_data)


@navdata_blueprint.route('/waypoint/<waypoint>')
def _get_waypoint(waypoint):
    client = g.mongo_nav_client
    waypoint_data = next(client.navdata.waypoints.find({'waypoint_id': waypoint}), None)
    return jsonify(waypoint_data)


@navdata_blueprint.route('/procedure/<procedure>')
def _get_procedure(procedure):
    client = g.mongo_nav_client
    procedure_data = next(client.navdata.procedures.find({'procedure': procedure}), None)
    return jsonify(procedure_data)
