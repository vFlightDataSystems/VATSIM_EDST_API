import logging
import re

import requests
from flask import g
from pymongo import MongoClient

import mongo_client
import libs.lib as lib
import libs.aar_lib as aar_lib
import libs.adr_lib as adr_lib
import libs.cache as cache


@cache.time_cache(300)
def get_artcc_adar(artcc: str, dep: str = '', dest: str = ''):
    response = requests.get(
        f'https://data-api.virtualnas.net/api/pdars?artccId={artcc.upper()}'
        f'&departureAirportId={dep.upper()}&destinationAirportId={dest.upper()}')
    return response.json()


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
        elif apt_data := client.navdata.airports.find_one({'icao': fix.upper()}, {'_id': False}):
            points.append({'name': apt_data['icao'], 'pos': (float(apt_data['lon']), float(apt_data['lat']))})
    return points


def get_edst_aar(artcc: str, aircraft: str, dest: str, alt: int, route: str) -> list:
    nat_list = set(lib.get_nat_types(aircraft) + ['NATALL'])
    aar_list = aar_lib.get_artcc_aar(artcc, dest)
    route_fixes = lib.get_route_fixes(route, [dest])
    available_aar = []
    for aar in aar_list:
        for tfix_details in aar['transitionFixesDetails']:
            fix = tfix_details['fix']
            if fix in route_fixes:
                aar['eligible'] = ((int(aar['minimumAltitude']) <= alt <= int(aar['topAltitude'])) or alt == 0) and \
                                  any(set(aar['aircraftClasses']).intersection(nat_list))
                amended_aar = aar_lib.amend_aar(route, aar)
                if amended_aar:
                    amended_aar['destination'] = dest
                    available_aar.append(amended_aar)
                break
    return available_aar


def get_edst_adr(artcc: str, dep: str, aircraft: str, alt: int, route: str) -> list:
    nat_list = set(lib.get_nat_types(aircraft) + ['NATALL'])
    adr_list = adr_lib.get_artcc_adr(artcc, dep)
    route_fixes = lib.get_route_fixes(lib.format_route(route), [dep])
    available_adr = []
    for adr in adr_list:
        for tfix in adr['transitionFixesDetails']:
            if tfix['fix'] in route_fixes:
                adr['eligible'] = ((int(adr['minimumAltitude']) <= alt <= int(adr['topAltitude'])) or alt == 0) and \
                                  any(set(adr['aircraftClasses']).intersection(nat_list))
                amended_adr = adr_lib.amend_adr(route, adr)
                if amended_adr:
                    amended_adr['departure'] = dep
                    available_adr.append(amended_adr)
                break
    return available_adr


def get_edst_adar(artcc: str, dep: str, dest: str, aircraft: str) -> list:
    nat_list = lib.get_nat_types(aircraft) + ['NATALL']
    adar_list = get_artcc_adar(artcc, dep, dest)
    ret_list = []
    for adar in adar_list:
        ret_list.append({
            'departure': dep,
            'destination': dest,
            'rnavRequired': adar['rnavRequired'],
            'eligible': any(set(adar['aircraftClasses']).intersection(nat_list)),
            'route': lib.format_route(adar['route']),
        })

    return ret_list
