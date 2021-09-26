from flask import g
from pymongo import MongoClient

import lib.lib


def slice_adr(route: list, expanded_route: list, tfix: str) -> list:
    """
    adjust a given adr which expands to expanded_route and have it end at a given tfix
    :param route: adr
    :param expanded_route: expanded adr
    :param tfix: transition fix
    :return: adr upto the transition fix
    """
    if route[-1] == tfix:
        return route[:-1]
    index = expanded_route.index(tfix)
    common_fixes = [e for e in route if e in expanded_route[:index]]
    slice_index = route.index(common_fixes[-1])
    return route[:slice_index]


def amend_adr(route: list, expanded_route: list, adr: dict) -> dict:
    """

    :param route:
    :param expanded_route:
    :param adr: adr dictionary as it is returned from the database
    :return: dictionary containing: the adr upto tfix, rest of the route starting after the tfix, route groups for the adr
    """
    adr_route = adr['route']
    # if adr matches initial route, there is nothing to do.
    if adr_route == route[:len(adr_route)]:
        adr_route = []
    else:
        expanded_adr = lib.lib.expand_route(adr_route, airways=adr['airways'])
        tfixes = adr['tfixes']
        fixes = [e['tfix'] for e in tfixes]
        info_dict = {e['tfix']: e['info'] for e in tfixes}
        for fix in reversed(expanded_route):
            # find farthest tfix which triggered the ADR
            if fix in fixes:
                info = info_dict[fix]
                if fix in route and 'Explicit' in info:
                    index = route.index(fix)
                    adr_route = slice_adr(adr_route, expanded_adr, fix)
                    if adr_route != route[:len(adr_route)]:
                        route = route[index:]
                    else:
                        adr_route = []
                    break
                elif 'Implicit' in info:
                    index = expanded_route.index(fix)
                    route_fix = [e for e in expanded_adr[index:] if e in route][-1]
                    route_index = route.index(route_fix)
                    adr_route = slice_adr(adr_route, expanded_adr, fix)
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
        'adr': adr_route,
        'route': route,
        'route_groups': adr['route_groups']
    }


def get_best_adr(dep: str, route: list, altitude: int, aircraft: str, equipment=None) -> list:
    # if route empty, do nothing, maybe implement crossing lines in the future
    client: MongoClient = g.mongo_fd_client
    nat_list = lib.lib.get_nat_types(aircraft) + ['NATALL']
    adr_list = list(client.flightdata.adr.find(
        {"dep": {"$in": [dep]},
         "aircraft_class": {"$elemMatch": {"$in": nat_list}}
         }, {'_id': False}))
    eligible_adr = []
    expanded_route = lib.lib.expand_route(route)
    for adr in adr_list:
        if (int(adr['min_alt']) < altitude < int(adr['top_alt'])) or altitude == 0:
            for tfix in adr['tfixes']:
                if (('Explicit' in tfix['info'] and
                     tfix['tfix'] in route) or
                        ('Implicit' in tfix['info'] and
                         tfix['tfix'] in expanded_route) or
                        (tfix['tfix'] in expanded_route and
                         tfix['info'] == 'Append')):
                    eligible_adr.append(adr)
                    break
    return eligible_adr
