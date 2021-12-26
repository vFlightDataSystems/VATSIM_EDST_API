import json.decoder
import pprint
import random
import re
from collections import defaultdict
from typing import Optional

import requests
from flask import g
from flask_caching import Cache
from pymongo import MongoClient

import config
import libs.adar_lib
import libs.adr_lib
import mongo_client
from resources.Flightplan import Flightplan

cache = Cache()
clean_route_pattern = re.compile(r'\+|/(.*?)\s|(\s?)DCT(\s?)|N[0-9]{4}[FAM][0-9]{3,4}')


def get_airports_in_artcc(artcc) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.get_reader_client()
    airports = client.navdata.airports.find({"artcc": artcc}, {'_id': False})
    return list(filter(None, [a['icao'] for a in airports]))


def get_nat_types(aircraft: str) -> list:
    """
    get all valid NAT type entries for given aircraft
    :param aircraft: aircraft icao code
    :return: aircraft nat types
    """
    client: MongoClient = g.mongo_reader_client if g else mongo_client.get_reader_client()
    nat_list = list(client.flightdata.nat_types.find({"aircraft_type": aircraft}, {'_id': False}))
    return [e['nat'] for e in nat_list]


def get_airway(airway: str) -> list:
    """
    get list of fixes on an airway
    :param airway: airway
    :return: list of all fixes in the airway (order matters!)
    """
    client: MongoClient = g.mongo_reader_client if g else mongo_client.get_reader_client()
    waypoints = list(sorted(client.navdata.airways.find(
        {"airway": {"$in": [airway]}}, {'_id': False}), key=lambda x: int(x['sequence'])))
    return waypoints


def get_airport_info(airport: str) -> dict:
    """
    get information for airport
    :param airport: ICAO code
    :return: information about given airport
    """
    client: MongoClient = g.mongo_reader_client if g else mongo_client.get_reader_client()
    airport_data = client.navdata.airports.find_one({'icao': airport.upper()}, {'_id': False})
    return airport_data


def format_route(route: str):
    client = g.mongo_reader_client if g else mongo_client.get_reader_client()
    route = route.split()
    new_route = ''
    prev_is_fix = True
    for s in route:
        is_fix = not (get_airway(s) or client.navdata.procedures.find_one({'procedure': s.upper()}, {'_id': False}))
        if prev_is_fix and is_fix:
            new_route += f'..{s}'
        else:
            new_route += f'.{s}'
        prev_is_fix = is_fix
    new_route += '..' if prev_is_fix else '.'
    return new_route


def get_airways_on_route(route: str):
    return list(filter(None, [get_airway(s) for s in route.split()]))


def expand_route(route: str, airways=None) -> str:
    """

    :param route:
    :param airways:
    :return:
    """
    route = route.split()
    if airways is None:
        airways = []
    new_route = []
    for i, segment in enumerate(route):
        if segment in airways or airways == []:
            awy = get_airway(segment)
            if awy and 0 < i < len(route):
                try:
                    sorted_awy = sorted(awy, key=lambda e: e['sequence'])
                    start_index = [e['wpt'] for e in sorted_awy].index(route[i - 1])
                    end_index = [e['wpt'] for e in sorted_awy].index(route[i + 1])
                    direction = 1 if end_index - start_index > 0 else -1
                    for s in sorted_awy[start_index + 1:end_index:direction]:
                        new_route.append(s['wpt'])
                except (ValueError, IndexError):
                    # if previous and next waypoint are not part of the airway, the airway is probably outside of the US
                    # with a duplicate name
                    # index error happens when the route ends in an airway...
                    new_route.append(segment)
            else:
                new_route.append(segment)
        else:
            new_route.append(segment)

    return ' '.join(new_route)


def clean_route(route, dep='', dest=''):
    if route:
        route = clean_route_pattern.sub(' ', route)
        route = re.sub(fr'{dep}|{dest}', "", route)
    return route.strip()


def get_faa_prd(dep: str, dest: str) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.get_reader_client()
    local_dep = re.sub(r'^K?', '', dep)
    local_dest = re.sub(r'^K?', '', dest)
    return list(client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))


def get_faa_cdr(dep: str, dest: str) -> list:
    client: MongoClient = g.mongo_reader_client
    return list(client.flightdata.faa_cdr.find({'dep': dep, 'dest': dest}, {'_id': False}))


def get_adar(dep: str, dest: str) -> list:
    dep_artcc = get_airport_info(dep)['artcc'].lower()
    client: MongoClient = g.mongo_reader_client if g else mongo_client.get_reader_client()
    return list(
        client[dep_artcc].adar.find({'dep': {'$in': [dep.upper()]}, 'dest': {'$in': [dest.upper()]}}, {'_id': False}))


def amend_flightplan(fp: Flightplan, active_runways=None) -> Flightplan:
    try:
        departing_runways = active_runways['departing'] if active_runways else None
    except KeyError:
        departing_runways = None

    if fp.departure and fp.route:

        adar_list = sorted(libs.adar_lib.get_eligible_adar(fp, departing_runways=departing_runways),
                           key=lambda x: (bool(x['ierr']), int(x['order'])), reverse=True)
        if adar_list and (any(filter(lambda x: x['ierr'], adar_list)) or not ('/L' in fp.aircraft_faa)):
            pprint.pprint(adar_list)
            if not any([a['route'] == fp.route for a in adar_list]):
                fp.amendment = f'{adar_list[0]["route"]}'
                fp.amended_route = f'+{adar_list[0]["route"]}+'
        else:
            adr_list = libs.adr_lib.get_eligible_adr(fp, departing_runways=departing_runways)
            adr_list = sorted(adr_list, key=lambda x: (bool(x['ierr']), int(x['order'])), reverse=True)
            adr_amendments = [libs.adr_lib.amend_adr(fp.route, adr) for adr in adr_list]
            if adr_amendments and not any([a['route'] == fp.route for a in adr_amendments]):
                adr = adr_amendments[0]
                if adr['adr_amendment']:
                    fp.amendment = f"{adr['adr_amendment']}"
                    fp.amended_route = f"+{adr['adr_amendment']}+ {adr['route']}"
    return fp


def assign_beacon(fp: Flightplan) -> Optional[str]:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.get_reader_client()
    code = None
    if fp and (dep_airport_info := client.navdata.airports.find_one({'icao': fp.departure}, {'_id': False})):
        arr_airport_info = client.navdata.airports.find_one({'icao': fp.arrival}, {'_id': False})
        dep_artcc = dep_airport_info['artcc']
        arr_artcc = arr_airport_info['artcc'] if arr_airport_info else None
        beacon_ranges = client.flightdata.beacons.find(
            {'artcc': dep_artcc, 'priority': {'$regex': r'I[PST]?-?\d*', '$options': 'i'}}, {'_id': False}) \
            if dep_artcc == arr_artcc else client.flightdata.beacons.find(
            {'artcc': dep_artcc, 'priority': {'$regex': r'E[PST]?-?\d*', '$options': 'i'}}, {'_id': False})
        codes_in_use = set(int(fp.assigned_transponder) for fp in get_all_flightplans().values())
        for entry in sorted(beacon_ranges, key=lambda b: b['priority']):
            start = int(entry['range_start'], 8)
            end = int(entry['range_end'], 8)
            if beacon_range := list(set(range(start, end)) - codes_in_use):
                code = f'{random.choice(beacon_range):o}'.zfill(4)
                break
    return code


@cache.cached(timeout=15, key_prefix='all_connections')
def get_all_connections() -> Optional[dict]:
    response = requests.get(config.VATSIM_DATA_URL)
    try:
        return response.json()
    except json.decoder.JSONDecodeError:
        return None


@cache.cached(timeout=15, key_prefix='all_pilots')
def get_all_pilots() -> list:
    if (connections := get_all_connections()) is not None:
        if 'pilots' in connections.keys():
            return connections['pilots']
    return []


@cache.cached(timeout=15, key_prefix='all_flightplans')
def get_all_flightplans() -> defaultdict:
    flightplans = defaultdict(None)
    for pilot in get_all_pilots():
        if flightplan := pilot['flight_plan']:
            fp = Flightplan(flightplan)
            fp.lat = pilot['latitude']
            fp.lon = pilot['longitude']
            fp.ground_speed = pilot['groundspeed']
            flightplans[pilot['callsign']] = fp
    return flightplans


@cache.cached(timeout=15, key_prefix='all_amended_flightplans')
def get_all_amended_flightplans() -> defaultdict:
    flightplans = get_all_flightplans()
    for callsign, fp in flightplans.items():
        flightplans[callsign] = amend_flightplan(fp)
    return flightplans


def get_flightplan(callsign: str) -> Flightplan:
    flightplans = get_all_flightplans()
    return flightplans[callsign] if callsign in flightplans.keys() else None
