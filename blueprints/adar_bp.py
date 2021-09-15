from flask import g, Blueprint, request, jsonify
from pymongo import MongoClient
from lib.adar_lib import get_best_adar

adar_blueprint = Blueprint('adar', __name__)


@adar_blueprint.route('/', methods=['POST'])
def _get_adar():
    """
    @:param airport : str
        airport for which to get adr
    @:param route_groups : str
        route groups to filter for
    :return:
    """
    fp = request.form.to_dict(flat=True)
    client: MongoClient = g.mongo_client
    dep: str = request.form.get('fp_departure')
    dest: str = request.form.get('fp_destination')
    route: str = request.form.get('fp_route')
    level = request.form.get('fp_level')
    altitude: int = int(level[1:]) * 100 if level[0] in ['F', 'A'] else 0
    aircraft: str = request.form.get('aircraft')
    equipment: list = request.form.get('fp_equipmentcode').split(',')
    route_groups = request.form.get('route_group')

    if route_groups:
        try:
            route_groups = set(int(rg) for rg in route_groups.split())
        except ValueError:
            route_groups = None

    if dep and dest:
        adar = get_best_adar(client, altitude, dep, dest, aircraft, route_groups)
        return jsonify(adar)
    else:
        return '', 204
