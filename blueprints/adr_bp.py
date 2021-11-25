from flask import Blueprint

adr_blueprint = Blueprint('adr', __name__)


@adr_blueprint.route('/', methods=['POST'])
def _get_adr():
    """

    :return:
    """
    return '', 204
