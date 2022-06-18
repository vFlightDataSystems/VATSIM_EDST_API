import logging
import re

import requests

import libs.lib as lib


def get_artcc_adr(artcc: str, airport: str = ''):
    response = requests.get(
        f'https://data-api.virtualnas.net/api/pdrs?artccId={artcc.upper()}&airportId={airport.upper()}')
    return response.json()


def truncate_route(route: str, route_fixes: list, tfix: str):
    remaining_route = route
    if tfix in route:
        remaining_route = route[route.index(tfix):]
    else:
        for fix in route_fixes[route_fixes.index(tfix):]:
            if fix in route:
                following_segment = route[fix + len(fix):].strip('.').split('.')[0]
                remaining_route = route[route.index(following_segment)]
                break
    return remaining_route


def amend_adr(route: str, adr: dict) -> dict:
    """

    :param route:
    :param adr: adr dictionary as it is returned from the database
    :return: dictionary containing: the adr upto tfix, rest of the route starting after the tfix, route groups for the adr
    """
    adr_route = adr['route']
    route = lib.format_route(route)
    route_fixes = lib.get_route_fixes(route, adr['airportIds'])
    triggered_tfix = None
    # if adr matches initial route, there is nothing to do.
    if adr_route == route[:len(adr_route)]:
        adr_route = ''
    else:
        tfixes = adr['transitionFixesDetails']
        for tfix in reversed(tfixes):
            fix = tfix['fix']
            # find farthest tfix which triggered the ADR
            if fix in route_fixes:
                triggered_tfix = tfix
                info = tfix['type']
                if info == 'Append':
                    break
                elif info == 'Explicit':
                    adr_route = adr_route[:adr_route.index(fix) + len(fix)]
                elif info == 'Implicit':
                    implicit_segment = tfix['implicitSegmentName']
                    adr_route = adr_route[:adr_route.index(implicit_segment) + len(implicit_segment)] + f'.{fix}'
                break

    return {
        'adr_amendment': adr_route,
        'tfix': triggered_tfix['fix'],
        'route': route,
        'eligible': adr['eligible'],
        'order': adr['order'],
        'route_groups': adr['route_groups']
    } if triggered_tfix else None
