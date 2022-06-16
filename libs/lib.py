import re
from math import pi
import requests
from flask import g
from pymongo import MongoClient
from haversine import inverse_haversine, Unit

import config
import mongo_client

clean_route_pattern = re.compile(r'\+|/(.*?)\s|(\s?)DCT(\s?)|N[0-9]{4}[FAM][0-9]{3,4}')


def get_airports_in_artcc(artcc: str) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    airports = client.navdata.airports.find({"artcc": artcc.upper()}, {'_id': False})
    return list(filter(None, [a['icao'] for a in airports]))


def get_nat_types(aircraft: str) -> list:
    """
    get all valid NAT type entries for given aircraft
    :param aircraft: aircraft icao code
    :return: aircraft nat types
    """
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    nat_list = list(client.flightdata.nat_types.find({"aircraft_type": aircraft}, {'_id': False}))
    return [e['nat'] for e in nat_list]


def get_airway(airway: str) -> list:
    """
    get list of fixes on an airway
    :param airway: airway
    :return: list of all fixes in the airway (order matters!)
    """
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    waypoints = list(sorted(client.navdata.airways.find(
        {"airway": {"$in": [airway]}}, {'_id': False}), key=lambda x: int(x['sequence']))) or \
                list(sorted(client.navdata.oceanic_airways.find({"airway": {"$in": [airway]}}, {'_id': False}),
                            key=lambda x: int(x['sequence'])))
    return waypoints


def get_airport_info(airport: str) -> dict:
    """
    get information for airport
    :param airport: ICAO code
    :return: information about given airport
    """
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    airport_data = client.navdata.airports.find_one({'icao': airport.upper()}, {'_id': False})
    return airport_data


def format_route(route: str):
    route = re.sub(r'\.+', ' ', route).strip().split()
    new_route = ''
    prev_is_fix = True
    for s in route:
        is_fix = True
        if prev_is_fix and is_fix:
            new_route += f'..{s}'
        else:
            new_route += f'.{s}'
        prev_is_fix = is_fix
    new_route += f'{"." if prev_is_fix else ""}.'
    return new_route


def get_airways_on_route(route: str):
    return list(filter(None, [get_airway(s) for s in route.split()]))


def expand_route(route: str, airports=None) -> list:
    """

    :param airports:
    :param route:
    :return:
    """
    if airports is None:
        airports = []
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    route = list(filter(None, re.split(r'\s|\.', route)))
    new_route = []
    prev_segment = None
    for i, segment in enumerate(route):
        if segment[-1].isdigit() and (awy := get_airway(segment)):
            if 0 < i < len(route):
                try:
                    sorted_awy = sorted(awy, key=lambda e: int(e['sequence']))
                    start_index = [e['wpt'] for e in sorted_awy].index(route[i - 1])
                    end_index = [e['wpt'] for e in sorted_awy].index(route[i + 1])
                    direction = 1 if end_index - start_index > 0 else -1
                    for j in range(start_index, end_index, direction):
                        new_route.append(sorted_awy[j]['wpt'])
                except (ValueError, IndexError):
                    # if previous and next waypoint are not part of the airway, the airway is probably outside of the US
                    # with a duplicate name
                    # index error happens when the route ends in an airway...
                    new_route.append(segment)
            else:
                new_route.append(segment)
        elif segment[-1].isdigit() and \
                (procedure := client.navdata.procedures.find_one(
                    {'procedure': segment.upper(), 'airport': {'$in': airports}}, {'_id': False})):
            if transitions := [r for r in procedure['routes'] if
                               not r['transition'] or r['transition'] in [prev_segment, 'ALL']]:
                # transitions.reverse()
                for transition in transitions:
                    new_route += transition['route']
            else:
                new_route.append(segment)
        else:
            new_route.append(segment)
        prev_segment = segment
    # remove duplicates
    return list(dict.fromkeys(new_route))


def clean_route(route, dep='', dest=''):
    if route:
        route = clean_route_pattern.sub(' ', route)
        route = re.sub(fr'^{dep}\S*|{dest}\S*$', "", route).strip()
    return route.strip()


def get_faa_prd(dep: str, dest: str) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    local_dep = re.sub(r'^K?', '', dep)
    local_dest = re.sub(r'^K?', '', dest)
    return list(client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))


def get_faa_cdr(dep: str, dest: str) -> list:
    client: MongoClient = g.mongo_reader_client
    return list(client.flightdata.faa_cdr.find({'dep': dep, 'dest': dest}, {'_id': False}))


def get_all_adar(dep: str, dest: str) -> list:
    dep_artcc = get_airport_info(dep)['artcc'].lower()
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    return list(
        client[dep_artcc].adar.find({'dep': {'$in': [dep.upper()]}, 'dest': {'$in': [dest.upper()]}}, {'_id': False}))


def get_frd_coordinates(lat: float, lon: float, bearing: float, distance: float):
    inverse_haversine_coords = list(
        inverse_haversine((lat, lon), distance, (pi * bearing / 360 + pi) % 2 * pi, unit=Unit.NAUTICAL_MILES))
    return list(reversed(inverse_haversine_coords))
