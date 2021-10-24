from flask import g
from pymongo import MongoClient

import lib.lib


def slice_adr(route: str, tfix: str) -> str:
    """
    adjust a given adr which expands to expanded_route and have it end at a given tfix
    :param route: adr
    :param tfix: transition fix
    :return: adr upto the transition fix
    """
    expanded_route = lib.lib.expand_route(route)
    route = route.split()
    if route[-1] == tfix:
        return ' '.join(route[:-1])
    index = expanded_route.index(tfix)
    return ' '.join(route[:index])


def amend_adr(route: str, adr: dict) -> dict:
    """

    :param route:
    :param adr: adr dictionary as it is returned from the database
    :return: dictionary containing: the adr upto tfix, rest of the route starting after the tfix, route groups for the adr
    """
    adr_route = adr['route']
    # if adr matches initial route, there is nothing to do.
    if adr_route == route[:len(adr_route)]:
        adr_route = ''
    else:
        expanded_adr = lib.lib.expand_route(adr_route, airways=adr['airways'])
        tfix_list = adr['tfixes']
        tfixes = [e['tfix'] for e in tfix_list]
        info_dict = {e['tfix']: e['info'] for e in tfix_list}
        expanded_route = lib.lib.expand_route(route).split()
        for fix in reversed(expanded_route):
            # find farthest tfix which triggered the ADR
            if fix in tfixes:
                info = info_dict[fix]
                if fix in route and 'Explicit' in info:
                    index = route.index(fix)
                    adr_route = slice_adr(adr_route, fix)
                    if adr_route != route[:len(adr_route)]:
                        route = route[index:]
                    else:
                        adr_route = ''
                    break
                elif 'Implicit' in info:
                    index = expanded_route.index(fix)
                    route_fix = [e for e in expanded_adr[index:] if e in route][-1]
                    route_index = route.index(route_fix)
                    adr_route = slice_adr(adr_route, fix)
                    if adr_route != route[:len(adr_route)]:
                        route = route[route_index:]
                    else:
                        adr_route = []
                    break
                elif info == 'Append':
                    index = expanded_route.index(fix)
                    route_fix = [e for e in expanded_route[index:] if e in route][0]
                    route_index = route.index(route_fix)
                    if adr_route != route[:len(adr_route)]:
                        route = route[route_index:]
                    else:
                        adr_route = []
                    break
    return {
        'adr_amendment': adr_route,
        'route': route,
        'order': adr['order'],
        'route_groups': adr['route_groups']
    }


def get_eligible_adr(fp) -> list:
    # if route empty, do nothing, maybe implement crossing lines in the future
    client: MongoClient = g.mongo_fd_client
    filed_alt = int(fp.altitude)
    nat_list = lib.lib.get_nat_types(fp.aircraft_short) + ['NATALL']
    adr_list = list(client.flightdata.adr.find(
        {"dep": fp.departure,
         "aircraft_class": {"$elemMatch": {"$in": nat_list}}
         }, {'_id': False}))
    eligible_adr = []
    expanded_route = lib.lib.expand_route(fp.route)
    for adr in adr_list:
        if (int(adr['min_alt']) <= filed_alt <= int(adr['top_alt'])) or filed_alt == 0:
            for tfix in adr['tfixes']:
                if (('Explicit' in tfix['info'] and
                     tfix['tfix'] in fp.route) or
                        ('Implicit' in tfix['info'] and
                         tfix['tfix'] in expanded_route) or
                        (tfix['tfix'] in expanded_route and
                         tfix['info'] == 'Append')):
                    eligible_adr.append(adr)
                    break
    return eligible_adr
