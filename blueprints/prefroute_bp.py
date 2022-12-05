import re
from flask import g, Blueprint, request, jsonify
from pymongo import MongoClient

prefroute_blueprint = Blueprint('prefroute', __name__)


@prefroute_blueprint.route('/<dep>/<dest>', methods=['GET', 'POST'])
def _get_prefroute(dep: str, dest: str):
    """
    @:param airport : str
        airport for which to get adr
    @:param route_groups : str
        route groups to filter for
    :return:
    """
    altitude = None
    aircraft = None
    equipment = None
    route_groups = None
    if request.method == 'POST':
        altitude = request.form.get('altitude', default=None)
        aircraft = request.form.get('aircraft', default=None)
        equipment = request.form.get('equipment', default=None)
        route_groups = request.form.get('route_group', default=None)

    client: MongoClient = g.mongo_fd_client

    adar_list = list(
        client.flightdata.adar.find({'dep': {'$in': [dep.upper()]}, 'dest': {'$in': [dest.upper()]}}, {'_id': False}))
    for adar in adar_list:
        adar['source'] = 'adar'

    local_dep = re.sub(r'^K?', '', dep)
    local_dest = re.sub(r'^K?', '', dest)
    faa_prd_list = list(
        client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))
    for prd in faa_prd_list:
        prd['source'] = 'faa'

    if route_groups:
        try:
            route_groups = set(int(rg) for rg in route_groups.split())
        except ValueError:
            route_groups = None

    return jsonify(adar_list + faa_prd_list)
