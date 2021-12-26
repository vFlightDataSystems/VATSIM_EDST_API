from flask import Blueprint, jsonify, request

import libs.lib
import libs.edst_lib
import mongo_client

EDST_KEYS = ['aircraft', 'type', 'equipment', 'route', 'altitude', 'interim', 'hdg', 'spd', 'hold_hdg', 'hold_spd', 'scatchpad']

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
    callsign = request.form.get('callsign', default=None)
    data = {}
    for key in EDST_KEYS:
        if v := request.form.get(key, default=None):
            data[key] = v
    ret_data = libs.edst_lib.update_edst_entry(callsign, data)
    return jsonify(ret_data)


@edst_blueprint.route('/all')
def _get_all_edst():
    data = libs.edst_lib.get_edst_data()
    return jsonify(data)


@edst_blueprint.route('/route/remaining_route/<callsign>')
def _get_remaining_route(callsign):
    data = libs.edst_lib.get_remaining_route(callsign)
    route = libs.lib.format_route(' '.join([e['fix'] for e in data])) if data else None
    return jsonify({'data': data, 'route': route})
