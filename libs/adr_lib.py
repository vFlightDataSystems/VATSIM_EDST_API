import logging
import re

from flask import g
from pymongo import MongoClient

import libs.lib
import mongo_client
from resources.Flightplan import Flightplan


def amend_adr(route: str, adr: dict) -> dict:
    """

    :param route:
    :param adr: adr dictionary as it is returned from the database
    :return: dictionary containing: the adr upto tfix, rest of the route starting after the tfix, route groups for the adr
    """
    route = libs.lib.format_route(route)
    adr_route = adr['route']
    # if adr matches initial route, there is nothing to do.
    if adr_route == route[:len(adr_route)]:
        adr_route = ''
    else:
        expanded_adr = adr['route_fixes']
        tfixes = adr['transition_fixes']
        tfix_info_dict = {e['tfix']: e['info'] for e in adr['transition_fixes_details']}
        for tfix in reversed(tfixes):
            # find farthest tfix which triggered the ADR
            tfix_info = tfix_info_dict[tfix]
            if tfix in route:
                if 'Append' in tfix_info:
                    route = route[route.index(tfix):]
                    break
                elif 'Explicit' in tfix_info:
                    dot_counter = int(tfix_info.split('-')[-1])
                    adr_route = ('.' + re.split(r'\.', adr_route[::-1], adr_route.count('.') - dot_counter)[-1])[::-1] \
                        .rstrip('.')
                    route = route[route.index(tfix) + len(tfix):]
                    break
            if 'Implicit' in tfix_info:
                try:
                    dot_counter, implicit_trigger = tfix_info.split('-')[0:]
                    adr_route = ('.' + re.split(r'\.', adr_route[::-1],
                                                adr_route.count('.') - int(dot_counter))[-1])[::-1]
                    index = route.index(implicit_trigger)
                    if index:
                        route = route[index:]
                    else:
                        route_fix = [e for e in expanded_adr if e in route][0]
                        route = route[route.index(route_fix) + len(tfix):]
                    break
                except (IndexError, ValueError) as e:
                    logging.Logger(str(e))
                    pass
    return {
        'adr_amendment': adr_route,
        'route': route,
        'order': adr['order'],
        'route_groups': adr['route_groups']
    }


def get_eligible_adr(fp: Flightplan, departing_runways=None) -> list:
    # if route empty, do nothing, maybe implement crossing lines in the future
    dep_info = libs.lib.get_airport_info(fp.departure)
    if not dep_info:
        return []
    dep_artcc = dep_info['artcc'].lower()
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    nat_list = libs.lib.get_nat_types(fp.aircraft_short) + ['NATALL']
    adr_list = client[dep_artcc].adr.find(
        {"dep": fp.departure,
         "aircraft_class": {"$elemMatch": {"$in": nat_list}}
         }, {'_id': False})
    eligible_adr = []
    dep_procedures = [
        p['procedure'] for p in
        client.navdata.procedures.find({'routes': {'$elemMatch': {'airports': fp.departure.upper()}}},
                                       {'_id': False})
        if departing_runways is None or any(
            [re.match(rf'RW{rw}|ALL', r['transition']) for r in p['routes'] for rw in departing_runways])
    ]
    alt = int(fp.altitude) * 100
    split_route = fp.route.split()
    expanded_route = libs.lib.expand_route(libs.lib.format_route(fp.route)).split()
    for adr in adr_list:
        dp = adr['dp']
        # check if adr is valid in current configuration
        if departing_runways and dep_procedures and dp and not any(p == dp for p in dep_procedures):
            continue
        if (int(adr['min_alt']) <= alt <= int(adr['top_alt'])) or alt == 0:
            for tfix_details in adr['transition_fixes_details']:
                if (('Explicit' in tfix_details['info'] and
                     tfix_details['tfix'] in split_route) or
                        ('Implicit' in tfix_details['info'] and
                         tfix_details['tfix'] in expanded_route) or
                        (tfix_details['tfix'] in expanded_route and
                         tfix_details['info'] == 'Append')):
                    eligible_adr.append(adr)
                    break
    return eligible_adr
