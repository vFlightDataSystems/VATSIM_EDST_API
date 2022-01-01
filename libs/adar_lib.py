import re

from pymongo import MongoClient
from flask import g

import libs.lib
import mongo_client
from resources.Flightplan import Flightplan


def check_adar_is_active(adar, fp: Flightplan, dep_procedures):
    valid_alt = not fp.altitude or int(adar['min_alt']) <= int(fp.altitude) <= int(adar['top_alt'])
    procedure_valid = not adar['dp'] or dep_procedures
    return valid_alt and procedure_valid


def get_eligible_adar(fp: Flightplan, departing_runways=None) -> list:
    """

    :return:
    """
    if departing_runways is None:
        departing_runways = []
    dep_info = libs.lib.get_airport_info(fp.departure)
    if not dep_info:
        return []
    dep_artcc = dep_info['artcc'].lower()
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    nat_list = libs.lib.get_nat_types(fp.aircraft_short) + ['NATALL']
    adar_list = client[dep_artcc].adar.find(
        {'dep': fp.departure, 'dest': fp.arrival, 'aircraft_class': {'$elemMatch': {'$in': nat_list}}},
        {'_id': False})
    dep_procedures = [
        p['procedure'] for p in
        client.navdata.procedures.find({'routes': {'$elemMatch': {'airports': fp.departure.upper()}}},
                                       {'_id': False})
        if departing_runways is None or any(
            [re.match(rf'RW{rw}|ALL', r['transition']) for r in p['routes'] for rw in departing_runways])
    ]
    return [adar for adar in adar_list if
            check_adar_is_active(adar, fp, dep_procedures)]
