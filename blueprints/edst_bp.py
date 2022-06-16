from collections import defaultdict

from flask import Blueprint, jsonify, request, g
from pymongo import MongoClient

import libs.lib as lib
import libs.edst_lib as edst_lib
import mongo_client

# TODO: write this list to database
EDST_KEYS = ['aircraft', 'type', 'equipment', 'route', 'route_data', 'altitude', 'interim', 'hdg', 'spd',
             'previous_route', 'previous_route_data',
             'hold_data', 'free_text_content', 'beacon', 'cleared_direct']

edst_blueprint = Blueprint('edst', __name__)


@edst_blueprint.before_request
def _get_mongo_clients():
    mongo_client.get_edst_mongo_client()


@edst_blueprint.after_request
def _close_mongo_clients(response):
    mongo_client.close_edst_mongo_client()
    return response


@edst_blueprint.route('/airports/<artcc>')
def _get_artcc_airports(artcc):
    return jsonify(lib.get_airports_in_artcc(artcc))


@edst_blueprint.route('/trial/route', methods=['POST'])
def _trial_route_amendment():
    post_data = defaultdict(None, request.get_json())
    keys = post_data.keys()
    amend_data = edst_lib.get_amended_route(route=post_data['route'],
                                            route_data=post_data['route_data'] if 'route_data' in keys else None,
                                            direct_fix=post_data['direct_fix'] if 'direct_fix' in keys else None,
                                            frd=post_data['frd'] if 'frd' in keys else None,
                                            dest=post_data['dest'] if 'dest' in keys else None)
    return jsonify(amend_data) if amend_data else jsonify(204)


@edst_blueprint.route('/fav/<artcc>/ctr')
def _get_ctr_fav(artcc):
    data = edst_lib.get_ctr_fav_data(artcc)
    return jsonify(data)


@edst_blueprint.route('/fav/<artcc>/app')
def _get_app_fav(artcc):
    data = edst_lib.get_app_fav_data(artcc)
    return jsonify(data)


@edst_blueprint.route('/ctr_profiles/<artcc>')
def _get_ctr_profiles(artcc):
    data = edst_lib.get_ctr_profiles(artcc)
    return jsonify(data)


@edst_blueprint.route('/gpd/<artcc>/sectors')
def _get_gpd_sectors(artcc: str):
    client: MongoClient = g.mongo_reader_client
    data = list(client[artcc.lower()].gpd_sectors.find({}, {'_id': False}))
    return jsonify(data)


@edst_blueprint.route('/gpd/<artcc>/airports')
def _get_gpd_airports(artcc: str):
    client: MongoClient = g.mongo_reader_client
    data = list(client[artcc.lower()].gpd_airports.find({}, {'_id': False}))
    return jsonify(data)


@edst_blueprint.route('/gpd/<artcc>/navaids')
def _get_gpd_navaids(artcc: str):
    client: MongoClient = g.mongo_reader_client
    data = list(client[artcc.lower()].gpd_navaids.find({}, {'_id': False}))
    return jsonify(data)


@edst_blueprint.route('/gpd/<artcc>/waypoints')
def _get_gpd_waypoints(artcc: str):
    client: MongoClient = g.mongo_reader_client
    data = list(client[artcc.lower()].gpd_waypoints.find({}, {'_id': False}))
    return jsonify(data)


@edst_blueprint.route('/gpd/<artcc>/airways')
def _get_gpd_airways(artcc: str):
    client: MongoClient = g.mongo_reader_client
    data = list(client[artcc.lower()].gpd_airways.find({}, {'_id': False}))
    return jsonify(data)


@edst_blueprint.route('/reference_fixes/<artcc>')
def _get_reference_fix_list(artcc):
    client: MongoClient = g.mongo_reader_client
    data = list(client[artcc.lower()].reference_fixes.find({}, {'_id': False}))
    return jsonify(data)
