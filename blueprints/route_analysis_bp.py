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
