from flask import Blueprint, request, jsonify

import libs.lib as lib
import libs.edst_lib as edst_lib

route_analysis_blueprint = Blueprint('route', __name__)


@route_analysis_blueprint.route('/get_route_data', methods=['GET'])
def _get_route_data():
    route = request.args.get('route')
    dep = request.args.get('dep')
    dest = request.args.get('dest')
    route = lib.clean_route(route, dep or '', dest or '')
    return jsonify(edst_lib.get_route_data(lib.get_route_fixes(route, [dest, dep])))


@route_analysis_blueprint.route('/format_route', methods=['GET'])
def _format_route():
    route = request.args.get('route')
    dep = request.args.get('dep')
    dest = request.args.get('dest')
    route = lib.clean_route(route, dep or '', dest or '')
    return jsonify(lib.format_route(route))


@route_analysis_blueprint.route('/aar/<artcc>', methods=['GET'])
def _get_aar(artcc):
    route = request.args.get('route')
    aircraft = request.args.get('aircraft')
    dest = request.args.get('dest')
    alt = int(request.args.get('alt'))

    aar_data = edst_lib.get_edst_aar(artcc, aircraft, dest, alt, route)
    return jsonify(aar_data)


@route_analysis_blueprint.route('/adr/<artcc>', methods=['GET'])
def _get_adr(artcc):
    route = request.args.get('route')
    aircraft = request.args.get('aircraft')
    dep = request.args.get('dep')
    dest = request.args.get('dest')
    alt = int(request.args.get('alt'))

    adr_data = edst_lib.get_edst_adr(artcc, dep, dest, aircraft, alt, route)
    return jsonify(adr_data)


@route_analysis_blueprint.route('/adar/<artcc>', methods=['GET'])
def _get_adar(artcc):
    aircraft = request.args.get('aircraft')
    dep = request.args.get('dep')
    dest = request.args.get('dest')

    adar_data = edst_lib.get_edst_adar(artcc, dep, dest, aircraft)
    return jsonify(adar_data)
