from flask import Blueprint, jsonify, request

import libs.lib

flightplans_blueprint = Blueprint('flightplan', __name__)


@flightplans_blueprint.route('all')
def _get_all_flightplans():
    return jsonify({c: vars(fp) for c, fp in libs.lib.get_all_flightplans().items()})


@flightplans_blueprint.route('callsign/<callsign>')
def _get_flightplan(callsign):
    if fp := libs.lib.get_flightplan(callsign):
        return jsonify(vars(fp))
    else:
        return 404, ''


# @flightplans_blueprint.route('amendments/all')
# def _get_all_amended_flightplans():
#     return jsonify(libs.lib.get_all_amended_flightplans())


@flightplans_blueprint.route('amendments/callsign/<callsign>', methods=['POST', 'GET'])
def _get_amended_flightplan(callsign):
    active_runways = request.get_json()['active_runways'] if request.method == 'POST' else None
    if fp := libs.lib.get_flightplan(callsign):
        fp = libs.lib.amend_flightplan(fp, active_runways=active_runways)
        return jsonify(vars(fp))
    else:
        return 404, ''


@flightplans_blueprint.route('beacon/<callsign>')
def _assign_beacon(callsign: str):
    code = libs.lib.assign_beacon(libs.lib.get_flightplan(callsign.upper()))
    return jsonify({'beacon': code, 'callsign': callsign})
