import json

from bson import json_util
from flask import Blueprint, request, g, jsonify, Response
from pymongo import MongoClient

import libs.lib
from config import MONGO_URL
from resources.AdaptationProfile import AdaptationProfile

adaptation_blueprint = Blueprint('adaptation', __name__)


def get_client(user, password, db) -> MongoClient:
    return MongoClient(MONGO_URL,
                       username=user,
                       password=password,
                       authSource=db)


@adaptation_blueprint.route('profile/update', methods=['POST'])
def _update_profile():
    post_data = request.get_json()
    username = post_data['username']
    password = post_data['password']

    profile = AdaptationProfile(post_data)

    if profile.facility and profile.profile_name and \
            username and password:
        artcc = libs.lib.get_airport_info(profile.facility)['artcc'].lower()
        client: MongoClient = get_client(username, password, artcc)
        client[artcc].profiles.update_one({'profile_name': profile.profile_name},
                                          {'$set': vars(profile)},
                                          upsert=True)
        client.close()
        return Response(status=200)
    else:
        return Response(status=204)


@adaptation_blueprint.route('profile/get/<facility>')
def _get_profiles(facility: str):
    airport_data = libs.lib.get_airport_info(facility)
    artcc = airport_data['artcc'].lower()
    client: MongoClient = g.mongo_reader_client
    profiles = list(client[artcc].profiles.find({'facility': facility}, {'_id': False}))
    return jsonify(profiles)


@adaptation_blueprint.route('/adr/get/<artcc>')
def _get_adr(artcc):
    """

    :return:
    """
    client: MongoClient = g.mongo_reader_client
    adr_list = client[artcc].adr.find({})
    return jsonify(json.loads(json_util.dumps(adr_list)))


@adaptation_blueprint.route('/adar/get/<artcc>')
def _get_adar(artcc):
    """

    :return:
    """
    client: MongoClient = g.mongo_reader_client
    adr_list = client[artcc].adar.find({})
    return jsonify(json.loads(json_util.dumps(adr_list)))
