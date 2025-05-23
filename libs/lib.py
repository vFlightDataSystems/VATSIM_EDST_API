import re
from math import pi

import requests
from flask import g
from pymongo import MongoClient
from haversine import inverse_haversine, Unit
import libs.helpers as helpers
import libs.cache as cache

import mongo_client

clean_route_pattern = re.compile(r'\+|/(.*?)\s|(\s?)DCT(\s?)|N[0-9]{4}[FAM][0-9]{3,4}')


@cache.time_cache(300)
def get_aircraft_type_collection():
    response = requests.get('https://data-api.vnas.vatsim.net/api/aircraft-class-collections')
    return response.json()


def get_airports_in_artcc(artcc: str) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    airports = client.navdata.airports.find({"artcc": artcc.upper()}, {'_id': False})
    return list(filter(None, [a['icao'] for a in airports]))


@cache.time_cache(300)
def get_nat_types(aircraft: str) -> list:
    """
    get all valid NAT type entries for given aircraft
    :param aircraft: aircraft icao code
    :return: aircraft nat types
    """
    aircraft_type_collection = get_aircraft_type_collection()
    aircraft_type_classes = []
    for c in aircraft_type_collection:
        for t in c['classes']:
            if aircraft in t['aircraftTypes']:
                aircraft_type_classes.append(t['name'])
    return aircraft_type_classes


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
        is_fix = not helpers.matches_any_route_segment_format(s)
        if prev_is_fix and is_fix:
            new_route += f'..{s}'
        else:
            new_route += f'.{s}'
        prev_is_fix = is_fix
    new_route += f'{"." if prev_is_fix else ""}.'
    return new_route


def get_airways_on_route(route: str):
    return list(filter(None, [get_airway(s) for s in route.split()]))


def get_route_fixes(route: str, airports: list = None, dest: str = None) -> list:
    """

    :param airports:
    :param dest: destination airport
    :param route:
    :return:
    """
    if airports is None:
        airports = []
    if dest and dest not in airports:
        airports.append(dest)
    client: MongoClient = mongo_client.reader_client
    route = list(filter(None, re.split(r'\s|\.', route)))
    new_route = []
    prev_segment = None
    for i, segment in enumerate(route):
        if helpers.matches_airway_format(segment) and (awy := get_airway(segment)):
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
        elif helpers.matches_sid_star_format(segment) and \
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
    if dest:
        new_route.append(dest)
    # remove duplicates
    return list(dict.fromkeys(new_route))


def clean_route(route, dep='', dest=''):
    if route:
        route = clean_route_pattern.sub(' ', route)
        route = re.sub(fr'^\s*{dep}|{dest}\s*$', "", route)
    return route.strip()


def get_faa_prd(dep: str, dest: str) -> list:
    client: MongoClient = g.mongo_reader_client if g else mongo_client.reader_client
    local_dep = re.sub(r'^K?', '', dep)
    local_dest = re.sub(r'^K?', '', dest)
    return list(client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))


def get_faa_cdr(dep: str, dest: str) -> list:
    client: MongoClient = g.mongo_reader_client
    return list(client.flightdata.faa_cdr.find({'dep': dep, 'dest': dest}, {'_id': False}))


def get_frd_coordinates(lat: float, lon: float, bearing: float, distance: float):
    inverse_haversine_coords = list(
        inverse_haversine((lat, lon), distance, (pi * bearing / 360 + pi) % 2 * pi, unit=Unit.NAUTICAL_MILES))
    return list(reversed(inverse_haversine_coords))
