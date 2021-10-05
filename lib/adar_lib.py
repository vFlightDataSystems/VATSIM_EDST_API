from pymongo import MongoClient
from flask import g

import lib.lib


def check_adar_is_valid(adar, altitude, equipment=None):
    return int(adar['min_alt']) <= altitude <= int(adar['top_alt'])


def get_eligible_adar(fp) -> list:
    """

    :return:
    """
    client: MongoClient = g.mongo_fd_client
    nat_list = lib.lib.get_nat_types(fp.aircraft_short) + ['NATALL']
    adar_list = client.flightdata.adar.find(
        {'dep': fp.departure, 'dest': fp.destination, 'aircraft_class': {'$elemMatch': {'$in': nat_list}}},
        {'_id': False})
    return [adar for adar in adar_list if
            check_adar_is_valid(adar, fp.altitude)]
