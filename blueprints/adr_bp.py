from flask import g, Blueprint, request, jsonify
from pymongo import MongoClient

import lib.adr_lib
import lib.lib

adr_blueprint = Blueprint('adr', __name__)


@adr_blueprint.route('/', methods=['POST'])
def _get_adr():
    """

    :return:
    """
    return '', 204
