from flask import Blueprint, request, jsonify

import libs.lib as lib
import libs.edst_lib as edst_lib

route_analysis_blueprint = Blueprint('route', __name__)


@route_analysis_blueprint.route('/get_route_data', methods=['POST'])
def _get_route_data():
    post_data = request.get_json()
    route = post_data['route']
    dep = post_data['dep']
    dest = post_data['dest']
    route = lib.clean_route(route, dep or '', dest or '')
    return jsonify(edst_lib.get_route_data(lib.expand_route(route, [dest, dep])))


@route_analysis_blueprint.route('/format_route', methods=['POST'])
def _format_route():
    post_data = request.get_json()
    route = post_data['route']
    dep = post_data['dep']
    dest = post_data['dest']
    route = lib.clean_route(route, dep or '', dest or '')
    return jsonify(lib.format_route(route, dest, dep))


@route_analysis_blueprint.route('/aar/<artcc>/post', methods=['POST'])
def _get_aar(artcc):
    post_data = request.get_json()
    route = post_data['route']
    aircraft = post_data['aircraft']
    dest = post_data['dest']
    alt = int(post_data['alt'])

    aar_data = edst_lib.get_edst_aar_generic(artcc, aircraft, dest, alt, route)
    return jsonify(aar_data)


@route_analysis_blueprint.route('/adr/<artcc>', methods=['POST'])
def _get_adr(artcc):
    post_data = request.get_json()
    route = post_data['route']
    aircraft = post_data['aircraft']
    dep = post_data['dep']
    dest = post_data['dest']
    alt = int(post_data['alt'])

    adr_data = edst_lib.get_edst_adr_generic(artcc, dep, dest, aircraft, alt, route)
    return jsonify(adr_data)


@route_analysis_blueprint.route('/adar/<artcc>', methods=['POST'])
def _get_adar(artcc):
    post_data = request.get_json()
    aircraft = post_data['aircraft']
    dep = post_data['dep']
    dest = post_data['dest']

    adar_data = edst_lib.get_edst_adar_generic(artcc, dep, dest, aircraft)
    return jsonify(adar_data)
