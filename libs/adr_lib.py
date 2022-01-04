import logging
import re

from flask import g
from pymongo import MongoClient

import libs.lib
import mongo_client
from resources.Flightplan import Flightplan


def slice_adr(route: str, tfix: str) -> str:
    """
    adjust a given adr which expands to expanded_route and have it end at a given tfix
    :param route: adr
    :param tfix: transition fix
    :return: adr upto the transition fix
    """
    if tfix in route:
        return route[:route.index(tfix)]

    expanded_route = libs.lib.expand_route(route)
    split_route = route.split()

    expanded_route = expanded_route[:expanded_route.index(tfix)]
    # latest fix before tfix before airway starts
    last_fix = [f for f in expanded_route.split() if f in split_route][-1]
    return ' '.join(split_route[:split_route.index(last_fix) + 2])


def amend_adr(route: str, adr: dict) -> dict:
    """

    :param route:
    :param adr: adr dictionary as it is returned from the database
    :return: dictionary containing: the adr upto tfix, rest of the route starting after the tfix, route groups for the adr
    """
    split_route = route.split()
    adr_route = adr['route']
    # if adr matches initial route, there is nothing to do.
    if adr_route == route[:len(adr_route)]:
        adr_route = ''
    else:
        expanded_adr = libs.lib.expand_route(adr_route).split()
        expanded_route = libs.lib.expand_route(route).split()
        tfix_list = adr['tfixes']
        tfixes = [e['tfix'] for e in tfix_list]
        info_dict = {e['tfix']: e['info'] for e in tfix_list}
        for fix in reversed(expanded_route):
            # find farthest tfix which triggered the ADR
            if fix in tfixes:
                info = info_dict[fix]
                if fix in split_route and 'Explicit' in info:
                    route_index = split_route.index(fix)
                    adr_route = slice_adr(adr_route, fix)
                    if adr_route != route[:len(adr_route)]:
                        adr_route += ' ' + split_route[route_index]
                        route = ' '.join(split_route[route_index + 1:])
                    else:
                        adr_route = ''
                    break
                elif 'Implicit' in info:
                    try:
                        index = expanded_route.index(fix)
                        route_fix = [e for e in expanded_adr[index:] if e in route][-1]
                        route_index = split_route.index(route_fix)
                        adr_route = slice_adr(adr_route, fix)
                        if adr_route != route[:len(adr_route)]:
                            route = ' '.join(split_route[route_index:])
                        else:
                            adr_route = ''
                        break
                    except IndexError as e:
                        logging.Logger(str(e))
                        pass
                elif info == 'Append':
                    index = expanded_route.index(fix)
                    try:
                        route_fix = [e for e in expanded_route[index:] if e in split_route][0]
                    except IndexError:
                        adr_route = ''
                        break
                    route_index = split_route.index(route_fix)
                    if adr_route != route[:len(adr_route)]:
                        adr_route += ' ' + split_route[route_index]
                        route = ' '.join(split_route[route_index + 1:])
                    else:
                        adr_route = ''
                    break
    return {
        'adr_amendment': adr_route.strip(),
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
    alt = int(fp.altitude)
    split_route = fp.route.split()
    expanded_route = libs.lib.expand_route(' '.join(fp.route.split()[:7])).split()
    for adr in adr_list:
        dp = adr['dp']
        # check if adr is valid in current configuration
        if dep_procedures and dp and not any(p == dp for p in dep_procedures):
            continue
        if (int(adr['min_alt']) <= alt <= int(adr['top_alt'])) or alt == 0:
            for tfix in adr['tfixes']:
                if (('Explicit' in tfix['info'] and
                     tfix['tfix'] in split_route) or
                        ('Implicit' in tfix['info'] and
                         tfix['tfix'] in expanded_route) or
                        (tfix['tfix'] in expanded_route and
                         tfix['info'] == 'Append')):
                    eligible_adr.append(adr)
                    break
    return eligible_adr
