from flask import Blueprint, jsonify, request

import lib.lib

flightplans_blueprint = Blueprint('flightplan', __name__)


@flightplans_blueprint.route('all')
def _get_all_flightplans():
    return jsonify(lib.lib.get_all_flightplans())


@flightplans_blueprint.route('callsign/<callsign>')
def _get_flightplan(callsign):
    if fp := lib.lib.get_flightplan(callsign):
        return jsonify(fp)
    else:
        return 404, ''


@flightplans_blueprint.route('amendments/all')
def _get_all_amended_flightplans():
    return jsonify(lib.lib.get_all_amended_flightplans())


@flightplans_blueprint.route('amendments/callsign/<callsign>', methods=['POST', 'GET'])
def _get_amended_flightplan(callsign):
    active_runways = request.get_json()['active_runways'] if request.method == 'POST' else None
    if fp := lib.lib.get_flightplan(callsign):
        fp = lib.lib.amend_flightplan(fp, active_runways=active_runways)
        return jsonify(fp)
    else:
        return 404, ''
