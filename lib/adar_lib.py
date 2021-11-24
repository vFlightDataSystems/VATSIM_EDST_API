from pymongo import MongoClient
from flask import g

import lib.lib


def check_adar_is_active(adar, fp, dep_procedures):

    valid_alt = not fp.altitude or int(adar['min_alt']) <= int(fp.altitude) <= int(adar['top_alt'])
    procedure_valid = not adar['dp'] or dep_procedures
    return valid_alt and procedure_valid


def get_eligible_adar(fp, departing_runways=None) -> list:
    """

    :return:
    """
    client: MongoClient = g.mongo_fd_client
    nav_client: MongoClient = g.mongo_nav_client
    nat_list = lib.lib.get_nat_types(fp.aircraft_short) + ['NATALL']
    adar_list = client.flightdata.adar.find(
        {'dep': fp.departure, 'dest': fp.arrival, 'aircraft_class': {'$elemMatch': {'$in': nat_list}}},
        {'_id': False})
    dep_procedures = [p for p in nav_client.navdata.procedures.find(
        {'airports': {'$elemMatch': {'airport': fp.departure}}, 'type': 'DP'}, {'_id': False}
    ) if any(filter(lambda x: x['airport'] == fp.departure and set(departing_runways).intersection(x['runways']),
                    p['airports']))]
    return [adar for adar in adar_list if
            check_adar_is_active(adar, fp, dep_procedures)]
