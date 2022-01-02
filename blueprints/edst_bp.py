from flask import Blueprint, jsonify, request

import libs.lib
import libs.edst_lib
import mongo_client

EDST_KEYS = ['aircraft', 'type', 'equipment', 'route', 'route_data', 'altitude', 'interim', 'hdg', 'spd',
             'previous_route', 'previous_route_data',
             'hold_data', 'scratchpad', 'beacon']

edst_blueprint = Blueprint('edst', __name__)


@edst_blueprint.before_request
def _get_mongo_clients():
    mongo_client.get_edst_mongo_client()


@edst_blueprint.after_request
def _close_mongo_clients(response):
    mongo_client.close_edst_mongo_client()
    return response


def get_edst_entry(callsign):
    fp = libs.lib.get_flightplan(callsign)
    edst_data = libs.edst_lib.get_edst_entry(callsign)
    return {'fp': vars(fp), 'edst': edst_data}


@edst_blueprint.route('/entry/<callsign>')
def _get_entry(callsign):
    return jsonify(get_edst_entry(callsign))


@edst_blueprint.route('/entry/update', methods=['POST'])
def _update_entry():
    post_data = request.get_json()
    if not post_data or 'callsign' not in post_data.keys():
        return jsonify(204)
    callsign = post_data['callsign']
    data = {}
    for key in EDST_KEYS:
        if key in post_data.keys():
            data[key] = post_data[key]
    ret_data = libs.edst_lib.update_edst_entry(callsign, data)
    return jsonify(ret_data)


@edst_blueprint.route('/all')
def _get_all_edst():
    data = libs.edst_lib.get_edst_data()
    return jsonify(data)


@edst_blueprint.route('/boundary_data/<artcc>')
def _get_boundary_data(artcc):
    data = libs.edst_lib.get_boundary_data(artcc)
    return jsonify(data)
