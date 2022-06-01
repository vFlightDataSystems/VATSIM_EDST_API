from flask import Blueprint, request, jsonify

import libs.lib as lib

route_analysis_blueprint = Blueprint('route', __name__)


@route_analysis_blueprint.route('/', methods=['POST'])
def _route_analysis():
    """

    :return:
    """
    route: str = request.form.get('route')
    route = lib.clean_route(route)
    edt: str = request.form.get('edt')
    aircraft: str = request.form.get('aircraft')

    return jsonify(None)


@route_analysis_blueprint.route('/get_fixes', methods=['POST'])
def _get_route_fixes():
    post_data = request.get_json()
    route = post_data['route']
    dep = post_data['dep']
    dest = post_data['dest']
    route = lib.clean_route(route, dep or '', dest or '')
    return jsonify(lib.expand_route(route, airports=[dest, dep]))


@route_analysis_blueprint.route('/format_route', methods=['POST'])
def _format_route():
    post_data = request.get_json()
    route = post_data['route']
    dep = post_data['dep']
    dest = post_data['dest']
    route = lib.clean_route(route, dep or '', dest or '')
    return jsonify(lib.format_route(route, dest, dep))
