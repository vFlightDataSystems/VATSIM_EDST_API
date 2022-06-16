import logging
import re
from flask import g
from pymongo import MongoClient

import mongo_client
import libs.lib as lib
import libs.aar_lib as aar_lib
import libs.adr_lib as adr_lib

NM_CONVERSION_FACTOR = 0.86898
KM_NM_CONVERSION_FACTOR = 0.53996

time_mask = '%Y-%m-%d %H:%M:%S.%f'


def get_ctr_fav_data(artcc):
    client: MongoClient = g.mongo_reader_client
    fav_data = list(client[artcc.lower()].ctr_fav.find({}, {'_id': False}))
    return fav_data


def get_app_fav_data(artcc):
    client: MongoClient = g.mongo_reader_client
    fav_data = list(client[artcc.lower()].app_fav.find({}, {'_id': False}))
    return fav_data


def get_ctr_profiles(artcc):
    client: MongoClient = g.mongo_reader_client
    profiles = list(client[artcc.lower()].ctr_profiles.find({}, {'_id': False}))
    return profiles


def get_amended_route(route: str = None,
                      route_data: list = None,
                      direct_fix: str = None,
                      frd: dict = None,
                      dest: str = None):
    if route and direct_fix:
        if route_data is None:
            route_data = get_route_data(lib.expand_route(route, [dest] if dest else None))
        route_fixes = [e['name'] for e in route_data]
        frd_str = f'{frd["waypoint_id"]}{str(int(frd["bearing"])).zfill(3)}{str(int(frd["distance"])).zfill(3)}' \
            if frd else ''
        if direct_fix in route_fixes:
            index = route_fixes.index(direct_fix)
            route_data = route_data[index:]
            for fix in reversed(route_fixes[:index + 1]):
                if fix in route:
                    route = route[route.index(fix) + len(fix):]
                    if not route[0].isdigit():
                        route = f'{frd_str}..{direct_fix}' + route
                    else:
                        route = f'{frd_str}..{direct_fix}.{fix}' + route
                    break
            if frd:
                frd_pos = lib.get_frd_coordinates(float(frd["lat"]), float(frd["lon"]), float(frd["bearing"]),
                                                  float(frd["distance"]))
                route_data = [{'name': frd_str, 'pos': frd_pos}] + route_data
            amend_data = {'route': route, 'route_data': route_data}
            return amend_data
        else:
            return None
    elif route:
        if route_data is None:
            expanded_route = lib.expand_route(route)
            route_data = get_route_data(expanded_route)
        if frd:
            frd = f'{frd["waypoint_id"]}{str(int(frd["bearing"])).zfill(3)}{str(int(frd["distance"])).zfill(3)}'
            route = f'{frd}..{route}'
        amend_data = {'route': lib.format_route(route), 'route_data': route_data}
        return amend_data
    return None


def get_route_data(fixes: list) -> list:
    """

    :rtype: list
    """
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    points = []
    for fix in fixes:
        try:
            if match := re.match(r'(\w+)(\d{3})(\d{3})', fix):
                fixname, bearing, distance = match.groups()
                wpt = client.navdata.waypoints.find_one({'waypoint_id': fixname}, {'_id': False})
                frd_pos = lib.get_frd_coordinates(float(wpt["lat"]), float(wpt["lon"]), float(bearing), float(distance))
                points.append({'name': fix, 'pos': [float(frd_pos[0]), float(frd_pos[1])]})
        except Exception as e:
            print(e)
            logging.Logger(str(e))
        if fix_data := client.navdata.waypoints.find_one({'waypoint_id': fix}, {'_id': False}):
            points.append({'name': fix, 'pos': (float(fix_data['lon']), float(fix_data['lat']))})
    return points


def get_edst_aar_generic(artcc: str, aircraft: str, dest: str, alt: int, route: str, ) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    nat_list = set(lib.get_nat_types(aircraft) + ['NATALL'])
    aar_list = client.flightdata.aar.find(
        {"airports": dest,
         "applicable_artcc": artcc.upper()}, {'_id': False})
    alt = alt if alt >= 1000 else alt * 100
    expanded_route = lib.expand_route(route, [dest])
    available_aar = []
    for aar in aar_list:
        for tfix_details in aar['transition_fixes_details']:
            tfix = tfix_details['tfix']
            tfix_info = tfix_details['info']
            is_procedure = False
            if tfix in route:
                is_procedure = route[route.index(tfix) + len(tfix)].isdigit() \
                    if len(route) > route.index(tfix) + len(tfix) else False
            if (('Explicit' in tfix_info and
                 tfix in route and
                 not is_procedure) or
                    ('Implicit' in tfix_info and
                     tfix in expanded_route) or
                    (tfix in expanded_route and
                     tfix_info == 'Prepend')):
                aar['eligible'] = ((int(aar['min_alt']) <= alt <= int(aar['top_alt'])) or alt == 0) and \
                                  any(set(aar['aircraft_class']).intersection(nat_list))
                aar['amendment'] = aar_lib.amend_aar(route, aar)
                available_aar.append(aar)
                break
    return available_aar


def get_edst_adr_generic(artcc: str, dep: str, dest: str, aircraft: str, alt: int, route: str) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    nat_list = set(lib.get_nat_types(aircraft) + ['NATALL'])
    adr_list = client[artcc].adr.find({"dep": dep}, {'_id': False})
    alt = alt if alt >= 1000 else alt * 100
    split_route = route.split()
    expanded_route = lib.expand_route(lib.format_route(route), [dep, dest])
    available_adr = []
    for adr in adr_list:
        for tfix_details in adr['transition_fixes_details']:
            if (('Explicit' in tfix_details['info'] and
                 tfix_details['tfix'] in split_route) or
                    ('Implicit' in tfix_details['info'] and
                     tfix_details['tfix'] in expanded_route) or
                    (tfix_details['tfix'] in expanded_route and
                     tfix_details['info'] == 'Append')):
                adr['eligible'] = ((int(adr['min_alt']) <= alt <= int(adr['top_alt'])) or alt == 0) and \
                                  any(set(adr['aircraft_class']).intersection(nat_list))
                adr['amendment'] = adr_lib.amend_adr(route, adr)
                available_adr.append(adr)
                break
    return available_adr


def get_edst_adar_generic(artcc: str, dep: str, dest: str, aircraft: str) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    nat_list = lib.get_nat_types(aircraft) + ['NATALL']
    adar_list = list(client[artcc].adar.find(
        {'dep': dep, 'dest': dest},
        {'_id': False}))
    for adar in adar_list:
        adar['eligible'] = any(set(adar['aircraft_class']).intersection(nat_list))
        adar['route_data'] = get_route_data(adar['route_fixes'])
        adar['route'] = lib.format_route(adar['route'])
    return adar_list
