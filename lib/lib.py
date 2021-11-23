import json.decoder
import re
from collections import defaultdict

from pymongo import MongoClient
import requests
from flask import g
from flask_caching import Cache

import lib.adr_lib
import lib.adar_lib
import config

cache = Cache()
clean_route_pattern = re.compile(r'\+|/(.*?)\s|(\s?)DCT(\s?)|N[0-9]{4}[FAM][0-9]{3,4}')


class ObjDict(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("No such attribute: " + name)

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError("No such attribute: " + name)


def get_nat_types(aircraft: str) -> list:
    """
    get all valid NAT type entries for given aircraft
    :param aircraft: aircraft icao code
    :return: aircraft nat types
    """
    client: MongoClient = g.mongo_fd_client
    nat_list = list(client.flightdata.nat_types.find({"aircraft_type": aircraft}, {'_id': False}))
    return [e['nat'] for e in nat_list]


def get_airway(airway: str):
    """
    get list of fixes on an airway
    :param airway: airway
    :return: list of all fixes in the airway (order matters!)
    """
    client = g.mongo_nav_client
    waypoints = list(sorted(client.navdata.airways.find(
        {"airway": {"$in": [airway]}}, {'_id': False}), key=lambda x: int(x['sequence'])))
    return waypoints


def get_apt_info(apt: str) -> dict:
    """
    get information for airport
    :param apt:
    :return: information about given airport
    """
    # remove leading 'K' for US airports
    apt = re.sub(r'^K', '', apt)
    return {}


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
    client = g.mongo_fd_client
    local_dep = re.sub(r'^K?', '', dep)
    local_dest = re.sub(r'^K?', '', dest)
    faa_prd_list = list(
        client.flightdata.faa_prd.find({'dep': local_dep, 'dest': local_dest}, {'_id': False}))
    for prd in faa_prd_list:
        prd['source'] = 'faa'
    return faa_prd_list


def get_adar(dep: str, dest: str) -> list:
    client = g.mongo_fd_client
    adar_list = list(
        client.flightdata.adar.find({'dep': {'$in': [dep.upper()]}, 'dest': {'$in': [dest.upper()]}}, {'_id': False}))
    for adar in adar_list:
        adar['source'] = 'adar'
    return adar_list


def amend_flightplan(fp: ObjDict, active_runways=None):
    try:
        departing_runways = active_runways['departing'] if active_runways else None
    except KeyError:
        departing_runways = None

    if fp.departure and fp.route:
        adr_list = lib.adr_lib.get_eligible_adr(fp, departing_runways=departing_runways)
        adar_list = sorted(lib.adar_lib.get_eligible_adar(fp, departing_runways=departing_runways),
                           key=lambda x: int(x['order']), reverse=True)
        adr_amendments = [lib.adr_lib.amend_adr(fp.route, adr) for adr in adr_list]
        adr_list = sorted(adr_amendments, key=lambda x: int(x['order']), reverse=True)
        if adar_list:
            if not any([a['route'] == fp.route for a in adar_list]):
                fp.best_route = f'+{adar_list[0]["route"]}+'
            fp.best_route = fp.route
        elif adr_list and not any([a['route'] == fp.route for a in adr_list]):
            adr = adr_list[0]
            if adr['adr_amendment']:
                fp.best_route = f"+{adr['adr_amendment']}+ {adr['route']}"
            else:
                fp.best_route = fp.route
        else:
            fp.best_route = fp.route
    return fp


@cache.cached(timeout=15, key_prefix='all_pilots')
def get_all_pilots():
    response = requests.get(config.VATSIM_DATA_URL)
    try:
        pilots = response.json()['pilots']
        return pilots
    except json.decoder.JSONDecodeError:
        return None


@cache.cached(timeout=15, key_prefix='all_flightplans')
def get_all_flightplans() -> defaultdict:
    flightplans = defaultdict(None)
    for pilot in get_all_pilots():
        if flightplan := pilot['flight_plan']:
            fp = ObjDict(flightplan)
            fp.route = clean_route(fp.route, fp.departure, fp.arrival)
            if not str(fp.altitude).isnumeric():
                fp.altitude = int(fp.altitude[2:] or 0) * 100
            flightplans[pilot['callsign']] = fp
    return flightplans


@cache.cached(timeout=15, key_prefix='all_amended_flightplans')
def get_all_amended_flightplans() -> defaultdict:
    flightplans = get_all_flightplans()
    for callsign, fp in flightplans.items():
        flightplans[callsign] = amend_flightplan(fp)
    return flightplans


def get_flightplan(callsign: str):
    return get_all_flightplans()[callsign]
