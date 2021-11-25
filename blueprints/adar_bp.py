from flask import Blueprint

adar_blueprint = Blueprint('adar', __name__)


@adar_blueprint.route('/', methods=['POST'])
def _get_adar():
    """
    :return:
    """
    return '', 204
