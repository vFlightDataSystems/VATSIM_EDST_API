from flask import Blueprint, request, g, jsonify, Response
from pymongo import MongoClient

import mongo_client
from resources.AdaptationProfile import AdaptationProfile

adaptation_blueprint = Blueprint('adaptation', __name__)


@adaptation_blueprint.before_request
def _get_adapt_client():
    mongo_client.get_adapt_mongo_client()


@adaptation_blueprint.after_request
def _close_adapt_client(response):
    mongo_client.close_adapt_mongo_client()
    return response


@adaptation_blueprint.route('profile/request', methods=['POST'])
def _request_profile():
    profile = AdaptationProfile(request.get_json())

    if facility := profile.facility and profile.profile_name:
        client: MongoClient = g.mongo_adapt_client
        client.adaptationProfiles.requests.insert(vars(profile))
        return Response(status=200)
    else:
        return Response(status=204)


@adaptation_blueprint.route('profile/get/<facility>')
def _get_profile(facility):
    client: MongoClient = g.mongo_adapt_client
    profile = client.adaptationProfiles[facility].find({}, {'_id': False})
    return jsonify(profile)
