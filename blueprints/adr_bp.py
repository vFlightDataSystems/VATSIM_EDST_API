import json

from bson import json_util
from flask import Blueprint, g, jsonify
from pymongo import MongoClient

adr_blueprint = Blueprint('adr', __name__)


@adr_blueprint.route('/get/artcc/<artcc>', methods=['GET'])
def _get_adr(artcc: str):
    """

    :return:
    """
    client: MongoClient = g.mongo_reader_client
    adr_list = client[artcc].adr.find({})
    return jsonify(json.loads(json_util.dumps(adr_list)))
