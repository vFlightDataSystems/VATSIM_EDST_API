from flask import Blueprint, jsonify, g

from lib.adr_lib import get_best_adr, amend_adr
from lib.lib import get_flightplan, expand_route, get_faa_prd, get_adar

flightplans_blueprint = Blueprint('flightplan', __name__)


@flightplans_blueprint.route('<callsign>')
def _get_flightplan(callsign):
    return jsonify(get_flightplan(callsign))


@flightplans_blueprint.route('amendments/<callsign>')
def _get_amended_flightplan(callsign):
    if fp := get_flightplan(callsign):
        if fp.departure and fp.route:
            split_route = fp.route.split()
            adr_list = get_best_adr(fp.departure, split_route, int(fp.altitude), fp.aircraft_short)
            adar_list = get_adar(fp.departure, fp.arrival)
            fp.amendments = dict()
            fp.amendments['adr'] = [amend_adr(split_route, expand_route(split_route), adr) for adr in adr_list]
            fp.amendments['adar'] = adar_list
            fp.amendments['faa_prd'] = get_faa_prd(fp.departure, fp.arrival)
    return jsonify(fp)
