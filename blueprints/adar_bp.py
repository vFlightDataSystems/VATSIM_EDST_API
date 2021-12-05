import json

from bson import json_util
from flask import Blueprint, g, jsonify
from pymongo import MongoClient

adar_blueprint = Blueprint('adar', __name__)


@adar_blueprint.route('/get/artcc/<artcc>', methods=['GET'])
def _get_adar(artcc):
    """

    :return:
    """
    client: MongoClient = g.mongo_reader_client
    adar_list = client[artcc].adar.find({})
    return jsonify(json.loads(json_util.dumps(adar_list)))
