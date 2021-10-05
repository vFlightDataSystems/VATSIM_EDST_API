from flask import Blueprint, request, jsonify
import lib.adar_lib
import lib.lib

adar_blueprint = Blueprint('adar', __name__)


@adar_blueprint.route('/', methods=['POST'])
def _get_adar():
    """
    :return:
    """
    return '', 204
