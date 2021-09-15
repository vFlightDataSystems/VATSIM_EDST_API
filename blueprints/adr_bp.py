from flask import g, Blueprint, request, jsonify
from pymongo import MongoClient

from lib.adr_lib import get_best_adr, amend_adr
from lib.lib import expand_route, clean_route

adr_blueprint = Blueprint('adr', __name__)


@adr_blueprint.route('/', methods=['POST'])
def _get_adr():
    """
    @:param airport : str
        airport for which to get adr
    @:param route_groups : str
        route groups to filter for
    :return:
    """
    fp = request.form.to_dict(flat=True)
    dep: str = request.form.get('fp_departure')
    route: str = request.form.get('fp_route')
    level = request.form.get('fp_level')
    altitude: int = int(level[1:])*100 if level[0] in ['F', 'A'] else 0
    aircraft: str = request.form.get('fp_aircrafttype')
    equipment: list = request.form.get('fp_equipmentcode').split(',')
    route_groups = request.form.get('route_group')
    route = clean_route(route)

    if route_groups:
        try:
            route_groups = set(int(rg) for rg in route_groups.split())
        except ValueError:
            route_groups = None

    if dep and route:
        split_route = route.split()
        expanded_route = expand_route(split_route)
        adr_list = get_best_adr(dep, split_route, altitude, aircraft, equipment)
        amended_routes = [amend_adr(split_route, expanded_route, adr) for adr in adr_list]
        return jsonify(amended_routes)
    else:
        return '', 204
